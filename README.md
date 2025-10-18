## AG2 Multi-Agent PoC Skeleton

本專案依照 `spec&doc/spec` 中的規格，建立 Master、LLM Gateway 與多個 Worker 的骨架，涵蓋資料契約、Redis 記憶體介面、路由/管線兩種調度策略與 Gemini/Bedrock 可替換的 LLM 呼叫流程。

### 目前內容
- `shared/schemas.py`：以 Pydantic 定義 Master 與 Worker 共享的 API payload（任務、子任務、結果、metrics、錯誤碼）。
- `shared/metrics.py`：MetricsRecorder / MetricsProvider 介面，用於 router 收集與評估代理的健康度。
- `master-agent/core/memory.py`：`RedisMemoryAdapter` 包裝註冊、子任務儲存、路由紀錄、結果與 context 存取，並實作 metrics 讀寫。
- `master-agent/ag2_controller/*`：`MasterDecomposer`、`AdaptiveRouterAgent` 與 `AG2Controller`，提供拆解與路由決策骨架。
- `master-agent/core/dispatcher.py` / `core/pipeline.py`：支援 routing 模式與 pipeline 模式（固定 A→B→C，並可動態追加 Finalizer D）。
- `master-agent/api/routes.py`、`master-agent/main.py`：FastAPI 入口，依 `MASTER_MODE` 自動載入對應策略。
- `llm-gateway`：獨立的 LLM Gateway 服務，統一包裝 Gemini / Bedrock / Mock 的呼叫流程。
- `agents/common/*`：Worker 共用基底（BaseAgent、Runtime、設定 dataclass、LLM Gateway client）。
- `agents/worker-{a,b,c,d}`：四個子代理（Analyzer / Retriever / Evaluator / Finalizer），啟動時自動註冊、維持心跳，透過 LLM Gateway 接受 `/work` 任務。

### Docker 快速啟動
1. 建立映像並啟動 Master + Redis + LLM Gateway + Workers：
   ```bash
   docker compose up --build
   ```
   - Master 服務：`http://localhost:8000`
   - LLM Gateway：`http://localhost:7000`
   - Worker-A：`http://localhost:5001`
   - Worker-B：`http://localhost:5002`
   - Worker-C：`http://localhost:5003`
   - Worker-D（Finalizer，可停用熱插拔）：`http://localhost:5004`
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
- 預設 `MASTER_MODE=pipeline`，同時提供 `routing` 模式，依需求切換環境變數即可。
- Pipeline 測試建議流程：
  1. 只啟動 A/B/C：`docker compose up --build master-agent llm-gateway worker-a worker-b worker-c redis`，呼叫 `POST /task`，流程應依序執行 A→B→C。
  2. 再啟動 Worker-D：`docker compose up --build worker-d`，再次呼叫 `POST /task`，流程應延伸為 A→B→C→D。
  3. 停掉 Worker-D (`docker compose stop worker-d`)，確認下一次請求又回到三階段。
- 若切換成 `MASTER_MODE=routing`，仍可透過 `POST /dispatch` 測試原本的能力導向路由。
- `POST /result` 主要留給 routing/async 模式使用；pipeline 模式已由 orchestrator 同步取得結果並寫回 Redis。

目前 LLM Gateway 預設使用 `mock` provider，若要串接 Gemini 請加上 `GEMINI_API_KEY`；改用 Bedrock 則需配置 `AWS_REGION` 與 `BEDROCK_MODEL_ID`。後續建議：
- 依實際需求擴充 routing 評分模型、累積長期統計並輸出至監控。
- 建立完整的整合測試（含 Worker-D 熱插拔、LLM 錯誤處理情境）。
- 視生產環境導入 Secrets Manager、TLS、WAF 等安全防護。
