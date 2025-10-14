## AG2 Multi-Agent PoC Skeleton

本專案依照 `spec&doc/spec` 中的規格，先建立 Master 與 Worker 之間的最小骨架，涵蓋資料契約、Redis 記憶體介面以及 Master 端的拆解與路由流程。

### 目前內容
- `shared/schemas.py`：以 Pydantic 定義 Master 與 Worker 共享的 API payload（任務、子任務、結果、metrics、錯誤碼）。
- `shared/metrics.py`：MetricsRecorder / MetricsProvider 介面，用於 router 收集與評估代理的健康度。
- `master-agent/core/memory.py`：`RedisMemoryAdapter` 原型，包裝註冊、子任務儲存、路由紀錄、結果與 context 存取，並實作 metrics 讀寫。
- `master-agent/ag2_controller/*`：`MasterDecomposer`、`AdaptiveRouterAgent` 與 `AG2Controller`，提供拆解與路由決策骨架。
- `master-agent/core/dispatcher.py`：串接 controller、routing service 與 memory，處理 `/task`、`/dispatch`、`/result` 三條流程。
- `master-agent/api/routes.py`、`master-agent/main.py`：FastAPI 入口，含依賴注入設定。
- `agents/common/*`：Worker 共用基底（BaseAgent、AG2Runtime、設定 dataclass）。
- `agents/worker-{a,b,c}`：三個子代理服務，分別載入分析 / 摘要 / 評估提示詞，啟動時自動註冊、維持心跳，並在 `/work` 接受任務後回傳結果到 Master。

### Docker 快速啟動
1. 建立映像並啟動 Master + Redis + Workers：
   ```bash
   docker compose up --build
   ```
   - Master 服務：`http://localhost:8000`
   - Worker-A：`http://localhost:5001`
   - Worker-B：`http://localhost:5002`
   - Worker-C：`http://localhost:5003`
   - Redis：`localhost:6379`
2. 服務停止：
   ```bash
   docker compose down
   ```

### 直接在主機測試（可選）
1. 安裝依賴（建議使用虛擬環境）：
   ```bash
   pip install -r master-agent/requirements.txt
   ```
2. 啟動 Redis（例如 `docker run -p 6379:6379 redis:7.2-alpine`）。
3. 啟動 Master 服務：
   ```bash
   uvicorn master-agent.main:app --reload
   ```

### API 測試流程
- Worker 啟動時會自動 `POST /register` 註冊至 Master；若要手動註冊，可直接呼叫該端點。
- `POST /task` 傳入任務目標，確認回傳的分解結果。
- `POST /dispatch` 傳入工作 payload，觀察日誌與 Redis 中的 `route:*`、`dispatch_log:*`、`results:*`。
- `POST /result` 模擬 worker 回報，確認 metrics 與結果列表是否更新。

目前 AG2 runtime 仍為 stub，Router 也採簡化 heuristic；建議的延伸方向：
- 導入真實的 AG2 流程（工具鏈、ReliableTool policy），替換現在的示範 runtime。
- 擴充 Router 的評分模型與觀測指標（如 latency、失敗率長期趨勢）。
- 針對失敗/超時建立重試與告警策略，並把結果寫回 Redis 供 Master 追蹤。
- 規劃自動化測試或整合測試腳本，確保 Docker Compose 場景能持續驗證。
