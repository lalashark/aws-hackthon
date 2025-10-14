## Sub Agent Specification v0.2

### 1. Objective
Define the unified structure and deployment plan for the three Sub Agents (worker-a, worker-b, worker-c) in the AG2-based multi-agent system. Each worker bundles an AG2 runtime but shares the same codebase and architecture, differing only in its system prompt and declared capability.

---

### 2. Overview
| Component | Description |
|------------|-------------|
| worker-a | Analytical agent that identifies patterns or insights in structured/unstructured data, backed by an embedded AG2 tool stack. |
| worker-b | Summarization agent that extracts key points and presents concise summaries, backed by an embedded AG2 tool stack. |
| worker-c | Evaluation agent that reviews and scores results for quality and correctness, backed by an embedded AG2 tool stack. |

All three agents share identical runtime structure, Dockerfile, AG2 integration, and API interfaces.

---

### 3. Common Architecture
| File | Role | Shared |
|------|------|--------|
| `base_agent.py` | Defines BaseAgent class and bridges FastAPI endpoints to the worker's AG2 agent | ✅ |
| `ag2_runtime.py` | Boots the embedded AG2 agent, registers tools, wraps ReliableTool policies | ✅ |
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
│   │   └── prompt_summarize.txt
│   ├── Dockerfile
│   └── requirements.txt
│
└── worker-c/
    ├── base_agent.py
    ├── main.py
    ├── ag2_runtime.py
    ├── config/
    │   └── prompt_evaluate.txt
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
| worker-b | `prompt_summarize.txt` | "You summarize information concisely and coherently, focusing on key ideas and logical flow." |
| worker-c | `prompt_evaluate.txt` | "You critically evaluate responses, judging correctness, clarity, and completeness with a confidence score." |

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
      - CAPABILITIES=["summarize"]
      - PROMPT_PATH=/app/config/prompt_summarize.txt
      - CALLBACK_URL=http://master-agent:8000/result
      - AG2_PROFILE=worker-summarize
    ports:
      - "5002:5000"

  worker-c:
    build: ./agents/worker-c
    environment:
      - AGENT_ID=worker-c
      - CAPABILITIES=["evaluate"]
      - PROMPT_PATH=/app/config/prompt_evaluate.txt
      - CALLBACK_URL=http://master-agent:8000/result
      - AG2_PROFILE=worker-evaluate
    ports:
      - "5003:5000"
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
- All sub agents share an identical code and deployment structure, each bundling its own AG2 runtime profile.
- Only the system prompt, declared capability, and `AG2_PROFILE` differ across workers.
- Simplifies container orchestration and scaling while keeping AG2 customization per worker lightweight.
- Future AG2 orchestration will control workflow logic; sub agents expose AG2 traces yet remain stateless at the HTTP boundary.

---

### 13. AG2 Integration Notes
- Workers launch an AG2 agent during startup, configured via `AG2_PROFILE` to load prompts, tools, and ReliableTool policies.
- Sub agents attach AG2 execution traces to `/result` payloads and persist them under `ag2:trace:<task_id>:<agent>` in Redis.
- Local retries, validation, and tool invocation flows are handled inside each worker to shield the master from transient errors.
