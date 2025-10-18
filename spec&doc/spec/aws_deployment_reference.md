## AWS 部署參考指引 v0.1

本文件提供將目前 AG2 Multi-Agent PoC 佈建到 AWS 的參考流程，從容器建置、映像儲存、網路拓樸、環境設定與觀測監控等面向進行說明。仍為 PoC 等級，正式導入時請依照組織安全與營運需求進一步強化。

### 1. 架構概覽
```
               +--------------------------+
               |      Amazon Route53      |
               +------------+-------------+
                            |
                      +-----v------+
                      |    ALB     |
                      +-----+------+
                            |
              +-------------+-------------+
              |                           |
      +-------v-------+           +-------v-------+
      | Master Service|           | Workers (EC2) |
      |   (ECS Fargate)|          |  Auto Scaling |
      +-------+-------+           +-------+-------+
              |                           |
              +-------------+-------------+
                            |
                    +-------v-------+
                    |  Amazon ElastiCache
                    |   (Redis Cluster)
                    +---------------+
```

- **Master Service**：部署於 ECS Fargate，負責 `/task`、`/dispatch`、`/result`。可設定最低 1 task、自動擴縮至 3 task。
- **Workers**：可選擇 ECS Fargate（每個 Worker 為獨立服務），或以 EC2 Auto Scaling 方式運行一組容器；本文件以 Fargate 為例。
- **Redis**：使用 Amazon ElastiCache for Redis (Cluster Mode Disabled) 做共享記憶體，建議開啟自動備份。
- **Networking**：建議 VPC 內部使用 Private Subnet，透過 NAT Gateway 對外存取映像與外部 API；ALB/Route53 只對 Master 的 `/task` 暴露公開端點。

### 2. 基礎設施準備
1. **VPC 與子網**  
   - 建立專用 VPC（例如 `10.20.0.0/16`），至少配置兩個私有子網供 Fargate 與 ElastiCache 使用。  
   - 若需公開入口，另外建立公共子網供 ALB/NAT 使用。
2. **安全群組**  
   - `sg-master`：允許 ALB → master (TCP 8000)，允許 Private Subnet 內部互訪。  
   - `sg-workers`：允許 master → workers (TCP 5000)，允許 Redis → workers (TCP 6379)。  
   - `sg-redis`：僅允許 `sg-master` 與 `sg-workers` 存取 TCP 6379。  
3. **IAM 角色**  
   - `ecsTaskExecutionRole`：具備讀取 ECR、CloudWatch Logs、Secrets Manager 權限。  
   - `ecsTaskRole`：若需要存取其他 AWS 資源（S3、Parameter Store），可視需求授權。

### 3. 容器映像流程
| 步驟 | 說明 |
|------|------|
| 1 | 建立 Amazon ECR Repositories，例如 `aws-hackthon/master-agent`、`aws-hackthon/worker-a` 等。 |
| 2 | 以 `docker buildx` 在 CI/CD 或本機完成建置並推送至 ECR。可沿用 `Dockerfile`，並於 `README` 中的 `docker compose` 指令改用 `aws ecr get-login-password` 進行登入。 |
| 3 | 若需跨區部署，建議在 CI 中使用 `--platform linux/amd64` 產製相容映像。 |

### 4. ECS Fargate 部署設定
| 服務 | 映像 | CPU/記憶體 | 域名/Port | 重要環境變數 |
|------|------|------------|-----------|--------------|
| master-agent | `aws_account.dkr.ecr.<region>.amazonaws.com/aws-hackthon/master-agent:latest` | 0.5 vCPU / 1GB | 8000 | `REDIS_HOST=<redis-endpoint>`, `REDIS_PORT=6379` |
| llm-gateway | `.../llm-gateway:latest` | 0.25 vCPU / 0.5GB | 7000 | `LLM_PROVIDER`, `GEMINI_API_KEY` 或 `AWS_REGION` |
| worker-a | `.../worker-a:latest` | 0.25 vCPU / 0.5GB | 5000 | `AGENT_ID=worker-a`, `MASTER_URL=http://master.internal:8000`, `LLM_GATEWAY_URL=http://llm-gateway.internal:7000` |
| worker-b | 同上 | 0.25 vCPU / 0.5GB | 5000 | `AGENT_ID=worker-b`, `CAPABILITIES=["retrieve"]`, `LLM_GATEWAY_URL=...` |
| worker-c | 同上 | 0.25 vCPU / 0.5GB | 5000 | `AGENT_ID=worker-c`, `CAPABILITIES=["evaluate"]`, `LLM_GATEWAY_URL=...` |
| worker-d (optional) | 同上 | 0.25 vCPU / 0.5GB | 5000 | `AGENT_ID=worker-d`, `CAPABILITIES=["finalize"]`, `LLM_GATEWAY_URL=...` |

- **Service Discovery**：建議使用 AWS Cloud Map 或內部 ALB 讓 Master 與 Workers 透過 DNS 尋址（例如 `worker-a.service.local`）。
- **Scaling Policy**：  
  - Master：CPU > 60% 或 RequestCount > 1000/min，自動擴展。  
  - Worker：依據 `redis` 中心跳/長期排隊量或 CloudWatch 自訂指標（例如 `/work` 5xx 數量）擴縮。  

### 5. Redis (ElastiCache) 設定
| 項目 | 建議設定 |
|------|-----------|
| Instance type | `cache.t4g.small` 起步，依工作量調整 |
| Engine | Redis 7.x (Cluster Mode disabled) |
| Parameter Group | 開啟 `appendonly yes`、設定 `notify-keyspace-events Ex` 用於事件 |
| Security | 啟用 Redis AUTH，並透過 Secrets Manager 注入 `REDIS_PASSWORD`；Fargate 任務要加上相對應環境變數 |
| Monitoring | 啟用 Enhanced Monitoring、Slow Log，並搭配 CloudWatch Alarm |

程式端需調整 `master-agent/main.py` 與 Workers `main.py` 在 Redis 連線時讀取 `REDIS_PASSWORD` 與 `REDIS_TLS`（若啟用 TLS）。  

### 6. CI/CD 建議流程
1. **建置**：使用 GitHub Actions or AWS CodeBuild 執行 `docker build`、`pytest`（若未來增加測試）。  
2. **安全掃描**：整合 Trivy 或 Amazon Inspector 掃描映像。  
3. **推送**：`docker push` 至對應 ECR。  
4. **部署**：使用 AWS CodeDeploy + ECS blue/green，或 GitHub Actions 透過 `aws ecs update-service --force-new-deployment` 滾動更新。  

### 7. 觀測與警示
| 類別 | 建議工具 | 指標 |
|------|-----------|------|
| 日誌 | CloudWatch Logs | `master-agent` 和 `worker-*` 的應用日誌；可設定 Subscription Filter 傳送至 OpenSearch |
| 指標 | CloudWatch Metrics | CPU/Mem、調整自訂指標（成功/失敗任務、Redis queue 長度） |
| Trace | AWS X-Ray (可選) | 若未來導入 AG2 tracing，可透過 X-Ray 整合 |
| 告警 | CloudWatch Alarm / SNS | Redis 連線失敗、任務失敗率 > 閾值、CPU 長時間 > 80% |

### 8. 安全與權限
- 於 ALB 建立 HTTPS Listener（ACM 憑證），Route53 將 `api.<domain>` 指向 ALB。  
- Worker 與 Master 的 `/task`、`/dispatch` 建議加上 API Key / JWT 甚至 Cognito 保護。  
- 使用 AWS WAF 過濾異常流量，並對 `/task` 速率限制。  
- 若需要存取外部 API，透過 Secrets Manager 或 Parameter Store 注入 Token，避免硬編碼。  

### 9. 成本估算（示例）
| 項目 | 假設 | 月費估算 (USD) |
|------|------|----------------|
| ECS Fargate | master 1 task、gateway 1 task、workers 4 task，0.25~0.5 vCPU | ~130 |
| ElastiCache Redis | cache.t4g.small (單節點) | ~35 |
| ALB | 低流量（50GB/月） | ~25 |
| NAT Gateway | 單 AZ | ~32 |
| CloudWatch Logs & Metrics | 依實際量計費 | 15 |
| **總計** | | **約 197**（僅供參考） |

### 10. 待辦與最佳實務
- 補強 AG2 Runtime 真實化後的資源需求，重新評估 Fargate 尺寸。  
- 將 Redis 操作包裝成層封裝，未來可切換到 DynamoDB、S3 等持久層。  
- 建立基礎整合測試，於 CI 中以 `docker compose` 模擬流程並產出健康報表。  
- 正式環境需考慮多區域容錯、災難復原（跨 AZ ElastiCache、ECS multi-AZ）。  

以上部署建議僅供參考，可依實際需求調整。丟到 `spec&doc/spec` 目錄便於搭配其他規格文件一併檢視。
