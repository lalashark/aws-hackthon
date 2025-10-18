## Sub Agent Specification v0.2

### 1. Objective
Define the unified structure and deployment plan for the core Sub Agents (worker-a, worker-b, worker-c) 與可熱插拔的 Finalizer (worker-d) in the AG2-based multi-agent system. 每個 worker 共用同一套程式骨架與 LLM Gateway 客戶端，僅透過系統提示詞與能力宣告來區分職責。

---

### 2. Overview
| Component | Description |
|------------|-------------|
| worker-a | Analyzer：解析使用者意圖、提煉需求重點。 |
| worker-b | Retriever：根據需求檢索可用資料或候選方案。 |
| worker-c | Evaluator：評估候選項目、提供排序與理由。 |
| worker-d | Finalizer（可選）：彙整前面結果並生成最終自然語言輸出。 |

四個 agents 共享相同的 runtime 結構、Dockerfile、LLM Gateway 整合與 API 介面。

---

### 3. Common Architecture
| File | Role | Shared |
|------|------|--------|
| `base_agent.py` | Defines BaseAgent class and bridges FastAPI endpoints to the worker's AG2 agent | ✅ |
| `ag2_runtime.py` | 透過 LLM Gateway 呼叫指定模型（Gemini / Bedrock / Mock），並封裝輸入/輸出格式 | ✅ |
| `main.py` | Launches FastAPI app, loads prompt, and runs BaseAgent | ✅ |
| `config/prompt_*.txt` | Defines each agent’s system prompt | ❌ |
| `Dockerfile` | Common build and run configuration | ✅ |
| `requirements.txt` | Python dependencies (FastAPI, Redis, Requests, AG2 SDK) | ✅ |

---

### 4. Directory Layout
```
agents/
├── worker-a/
│   ├── base_agent.py
│   ├── main.py
│   ├── ag2_runtime.py
│   ├── config/
│   │   └── prompt_analyze.txt
│   ├── Dockerfile
│   └── requirements.txt
│
├── worker-b/
│   ├── base_agent.py
│   ├── main.py
│   ├── ag2_runtime.py
│   ├── config/
│   │   └── prompt_retrieve.txt
│   ├── Dockerfile
│   └── requirements.txt
│
├── worker-c/
│   ├── base_agent.py
│   ├── main.py
│   ├── ag2_runtime.py
│   ├── config/
│   │   └── prompt_evaluate.txt
│   ├── Dockerfile
│   └── requirements.txt
│
└── worker-d/
    ├── base_agent.py
    ├── main.py
    ├── ag2_runtime.py
    ├── config/
    │   └── prompt_finalize.txt
    ├── Dockerfile
    └── requirements.txt
```

---

### 5. Core Behavior
| Function | Description |
|-----------|-------------|
| `register()` | Registers the agent with the master, sending `{agent_id, url, capabilities, ag2_profile}` |
| `/work` | Receives a task via POST `{task_id, command, data}` and passes execution to the embedded AG2 agent/toolchain |
| `callback()` | Sends task result to Master `/result` `{task_id, agent_id, output, status, ag2_trace}` |
| `heartbeat()` | Updates liveness status to Redis with TTL key `heartbeat:<agent>` |
| `local_memory` | Temporary in-process cache for task history |
| `global_memory` | Read-only shared Redis access for global context |

---

### 6. Communication Protocol
| Direction | Source | Destination | Method | Purpose |
|------------|----------|--------------|----------|----------|
| Master → Sub | Master | `/work` | POST | Assign task |
| Sub → Master | Sub | `/result` | POST | Return result |
| Sub → Master | Sub | `/register` | POST | Capability registration |
| Sub → Redis | Sub | `heartbeat:<agent>`, `ag2:trace:<task_id>:<agent>` | TTL / List | Liveness tracking + trace persistence |
| Master ↔ Redis | Shared | `routing`, `context`, `results`, `ag2:trace` | Read/Write | Shared state |

---

### 7. Redis Namespace
| Key | Type | Description |
|------|------|-------------|
| `routing` | Hash | agent_id → metadata (url, capabilities) |
| `cap_index:<cap>` | Set | Agents supporting a capability |
| `heartbeat:<agent>` | Key | TTL for liveness |
| `memory:<agent>` | List | Local log for debugging |
| `results:<task_id>` | List | Task results aggregation |
| `global:context` | Hash | Shared context |
| `ag2:trace:<task_id>:<agent>` | List | Serialized AG2 reasoning steps for auditing |

---

### 8. System Prompt Definitions
| Agent | Prompt File | System Prompt Summary |
|--------|--------------|--------------------------|
| worker-a | `prompt_analyze.txt` | "You are an analytical assistant that identifies patterns and insights in structured or unstructured data." |
| worker-b | `prompt_retrieve.txt` | "You retrieve relevant information, candidates, or facts that match the extracted intent." |
| worker-c | `prompt_evaluate.txt` | "You critically evaluate responses, judging correctness, clarity, and completeness with a confidence score." |
| worker-d | `prompt_finalize.txt` | "You synthesize prior stage outputs into a friendly, actionable final recommendation." |

---

### 9. Unified Dockerfile Template
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

---

### 10. docker-compose Example
```yaml
version: '3'
services:
  worker-a:
    build: ./agents/worker-a
    environment:
      - AGENT_ID=worker-a
      - CAPABILITIES=["analyze"]
      - PROMPT_PATH=/app/config/prompt_analyze.txt
      - CALLBACK_URL=http://master-agent:8000/result
      - AG2_PROFILE=worker-analyze
    ports:
      - "5001:5000"

  worker-b:
    build: ./agents/worker-b
    environment:
      - AGENT_ID=worker-b
      - CAPABILITIES=["retrieve"]
      - PROMPT_PATH=/app/config/prompt_retrieve.txt
      - CALLBACK_URL=http://master-agent:8000/result
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    ports:
      - "5002:5000"

  worker-c:
    build: ./agents/worker-c
    environment:
      - AGENT_ID=worker-c
      - CAPABILITIES=["evaluate"]
      - PROMPT_PATH=/app/config/prompt_evaluate.txt
      - CALLBACK_URL=http://master-agent:8000/result
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    ports:
      - "5003:5000"

  worker-d:
    build: ./agents/worker-d
    environment:
      - AGENT_ID=worker-d
      - CAPABILITIES=["finalize"]
      - PROMPT_PATH=/app/config/prompt_finalize.txt
      - CALLBACK_URL=http://master-agent:8000/result
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    ports:
      - "5004:5000"
```

---

### 11. Execution Flow
```
Startup → register() → declare capabilities
   ↓
Initialize AG2 runtime (load profile, tools, ReliableTool policies)
   ↓
Wait for /work → execute via BaseAgent.handle_task() via AG2 runtime
   ↓
POST /result → Master collects and stores in Redis
   ↓
(optional) heartbeat → Redis TTL refresh
```

---

### 12. Design Summary
- 所有 workers 共用基底程式，透過環境變數調整能力、提示詞與 LLM provider。
- Worker-A/B/C 為固定管線，Worker-D 作為可動態加入的 Finalizer；在 routing 模式下仍可依能力單獨調度。
- LLM Gateway 集中管理 Gemini / Bedrock / Mock 呼叫，Workers 只需組裝 prompt 與輸入資料。
- Redis 持續儲存結果、心跳與路由資訊，使 Master 能即時感知 Worker 的加入與離線。

---

### 13. LLM / Pipeline Integration Notes
- Workers 於啟動時載入對應 prompt，並透過 LLM Gateway 呼叫指定 provider；若切換至 Bedrock 只需調整 Gateway 環境設定。
- Pipeline 模式會使用同步 `reply_mode`，使 Master 能在 Worker 執行完畢後立即將結果送往下一階段；routing 模式仍沿用非同步 callback。
- Worker-D 的加入/離線只會更新 Redis `routing`，Master 會在下一次任務自動偵測是否需要加入 Finalizer。
