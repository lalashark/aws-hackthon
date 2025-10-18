## AG2 Multi-Agent PoC System Specification v0.1

### 1. System Objective
This specification defines the overall architecture of the AG2 multi-agent Proof of Concept (PoC). The system demonstrates modular, container-based orchestration where a Master Agent coordinates multiple Sub Agents through a Redis-based shared memory layer. It is designed for deployment on both local Docker environments and cloud infrastructure (AWS, GCP, Zeabur, etc.).

---

### 2. Core Components
| Component | Description | Container | Language |
|------------|-------------|------------|-----------|
| **Master Agent** | Performs task decomposition, adaptive routing, and result aggregation. | `master-agent` | Python (FastAPI) |
| **Sub Agents (x3)** | AG2-enabled worker modules with individual capabilities and local toolchains. | `worker-a`, `worker-b`, `worker-c` | Python (FastAPI) |
| **Memory Layer** | Shared Redis instance for routing, context, and heartbeat tracking. | `redis` | Redis 7.2-alpine |

---

### 3. System Topology
```
+--------------------------------------------------------------+
|                       Master Agent (Controller)              |
|  - Task decomposition                                        |
|  - Adaptive routing via AG2 logic                            |
|  - Result aggregation & Redis sync                           |
|                                                              |
|   +---------------------+  +---------------------+            |
|   |      Worker-A       |  |      Worker-B       |            |
|   | Capability: analyze |  | Capability: retrieve|            |
|   +---------------------+  +---------------------+            |
|                \\             /                               |
|                 \\           /                                |
|                 +---------------------+                       |
|                 |      Worker-C       |                       |
|                 | Capability: evaluate|                       |
|                 +---------------------+                       |
|                          |                                    |
|                          ↓                                    |
|                   (Optional) Worker-D                         |
|                   Capability: finalize                        |
|                          |                                    |
|                          ↓                                    |
|                     LLM Gateway                               |
|                   - Gemini / Bedrock                          |
|                   - Mock provider                             |
|                          |                                    |
|                          ↓                                    |
|                   Redis Memory Layer                         |
|                   - routing / results / context               |
|                   - pub/sub & TTL heartbeats                  |
+--------------------------------------------------------------+
```

---

### 4. Communication Overview
| Direction | Source | Destination | Protocol | Purpose |
|------------|----------|--------------|-----------|----------|
| Master → Sub | `master-agent` | `/work` endpoint | HTTP POST | Assign task |
| Sub → Master | `worker-*` | `/result` endpoint | HTTP POST | Return result |
| Sub → Master | `worker-*` | `/register` | HTTP POST or Redis publish | Register capability |
| Master ↔ Redis | Shared | `routing`, `context`, `results`, `ag2:trace` | TCP/Redis | Shared state management |
| Sub ↔ Redis | Shared | `heartbeat`, `agent_events`, `ag2:trace` | TCP/Redis | Health & event sync, trace persistence |

---

### 5. Data Flow
1. **Agent Registration** → `worker-x` → `/register` → Master → Redis `routing`
2. **Task Dispatch** → Master decomposes → `/work` → selected worker(s) → local AG2 runtime executes task
3. **Result Return** → `worker-*` → `/result` (payload includes AG2 trace + status) → Master → Redis `results:<task_id>`
4. **Context Sharing** → All agents access `global:context`
5. **Heartbeat Tracking** → Sub agents update TTL keys → Master monitors liveness

---

### 6. Container Summary
| Container | Role | Port | Depends On | Key Environment Variables |
|------------|------|------|-------------|-----------------------------|
| **master-agent** | Controller (routing / pipeline) | 8000 | redis, llm-gateway | `REDIS_HOST=redis`, `MASTER_MODE`, `LLM_GATEWAY_URL` |
| **llm-gateway** | LLM abstraction (Gemini / Bedrock / Mock) | 7000 | — | `LLM_PROVIDER`, `GEMINI_API_KEY`, `AWS_REGION` |
| **worker-a** | Analyzer | 5001 | redis, llm-gateway | `AGENT_ID=worker-a`, `CAPABILITIES=["analyze"]`, `PROMPT_PATH=/app/config/prompt_analyze.txt`, `LLM_GATEWAY_URL` |
| **worker-b** | Retriever | 5002 | redis, llm-gateway | `AGENT_ID=worker-b`, `CAPABILITIES=["retrieve"]`, `PROMPT_PATH=/app/config/prompt_retrieve.txt` |
| **worker-c** | Evaluator | 5003 | redis, llm-gateway | `AGENT_ID=worker-c`, `CAPABILITIES=["evaluate"]`, `PROMPT_PATH=/app/config/prompt_evaluate.txt` |
| **worker-d** | Finalizer (hot plug) | 5004 | redis, llm-gateway | `AGENT_ID=worker-d`, `CAPABILITIES=["finalize"]`, `PROMPT_PATH=/app/config/prompt_finalize.txt` |
| **redis** | Shared memory layer | 6379 | — | — |

---

### 7. Redis Schema
| Key | Type | Description |
|------|------|-------------|
| `routing` | Hash | agent_id → {url, capabilities} |
| `cap_index:<cap>` | Set | Reverse lookup by capability |
| `results:<task_id>` | List | Aggregated sub-agent outputs |
| `global:context` | Hash | Shared task context |
| `heartbeat:<agent>` | Key | TTL-based liveness |
| `agent_events` | Channel | Agent join/leave broadcast |
| `ag2:trace:<task_id>:<agent>` | List | Serialized reasoning trace returned by worker AG2 runtimes |

---

### 8. docker-compose Orchestration
```yaml
version: '3'
services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    networks: [agnet]

  master-agent:
    build: ./master
    ports:
      - "8000:8000"
    depends_on: [redis, llm-gateway]
    environment:
      - MASTER_MODE=pipeline
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    networks: [agnet]

  llm-gateway:
    build: ./llm-gateway
    ports:
      - "7000:7000"
    environment:
      - LLM_PROVIDER=mock
    networks: [agnet]

  worker-a:
    build: ./agents/worker-a
    ports:
      - "5001:5000"
    depends_on: [redis, master-agent, llm-gateway]
    environment:
      - AGENT_ID=worker-a
      - CAPABILITIES=["analyze"]
      - PROMPT_PATH=/app/config/prompt_analyze.txt
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    networks: [agnet]

  worker-b:
    build: ./agents/worker-b
    ports:
      - "5002:5000"
    depends_on: [redis, master-agent, llm-gateway]
    environment:
      - AGENT_ID=worker-b
      - CAPABILITIES=["retrieve"]
      - PROMPT_PATH=/app/config/prompt_retrieve.txt
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    networks: [agnet]

  worker-c:
    build: ./agents/worker-c
    ports:
      - "5003:5000"
    depends_on: [redis, master-agent, llm-gateway]
    environment:
      - AGENT_ID=worker-c
      - CAPABILITIES=["evaluate"]
      - PROMPT_PATH=/app/config/prompt_evaluate.txt
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    networks: [agnet]

  worker-d:
    build: ./agents/worker-d
    ports:
      - "5004:5000"
    depends_on: [redis, master-agent, llm-gateway]
    environment:
      - AGENT_ID=worker-d
      - CAPABILITIES=["finalize"]
      - PROMPT_PATH=/app/config/prompt_finalize.txt
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    networks: [agnet]

networks:
  agnet:
```

---

### 9. Scalability & Extensibility
| Area | Strategy |
|------|-----------|
| **Scaling Sub Agents** | Add new workers with unique `AGENT_ID` and capabilities; Master auto-registers them via Redis. |
| **Replacing Redis** | Redis can be swapped with AWS ElastiCache, DynamoDB, or Firestore via MemoryAdapter. |
| **Multi-Cloud Ready** | Supports Docker Compose, ECS, EKS, or Zeabur deployment. |
| **AG2 Integration** | Master runs AG2-based decomposition/routing; each worker hosts its own AG2 profile for tool execution and trace reporting. |

---

### 10. Security & Observability
| Area | Enhancement |
|------|-------------|
| Network Security | Isolated Docker network; TLS for Redis in production. |
| Authentication | Token-based API access (planned). |
| Monitoring | RedisInsight, Prometheus, and centralized logs. |
| Logging | Structured JSON logs for CloudWatch ingestion. |

---

### 11. Summary
- Containerized multi-agent PoC demonstrating modular AI orchestration.
- Master controls adaptive routing and task decomposition.
- Sub Agents act as independent AG2-enabled capability units with minimal coupling.
- Redis functions as a unified memory and event bus.
- Architecture is cloud-ready, extensible, and AG2-integrated across controller and workers.
