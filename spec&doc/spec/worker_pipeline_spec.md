## AG2 Multi-Worker Pipeline (Gemini Test Mode) — Spec v1.0

### 1. Overview

This document specifies the **local development and testing setup** for the AG2-based multi-agent pipeline using **Gemini API** as the LLM provider. The setup includes 1 Master Agent, 3 Sequential Workers (A/B/C), and 1 Hot-Pluggable Worker (D), coordinated via Redis. The design aims to simulate Bedrock-like reasoning orchestration before cloud deployment.

---

### 2. Architecture

**Service Composition:**
```
services/
├── master-agent/
│   ├── dispatcher.py
│   ├── routing.py
│   ├── ag2_controller/
│   │   ├── decomposer.py
│   │   └── adaptive_router.py
├── agents/
│   ├── worker-a/
│   │   ├── main.py
│   │   ├── llm_client.py
│   │   └── config/prompt_analyze.txt
│   ├── worker-b/
│   │   ├── main.py
│   │   ├── llm_client.py
│   │   └── config/prompt_retrieve.txt
│   ├── worker-c/
│   │   ├── main.py
│   │   ├── llm_client.py
│   │   └── config/prompt_evaluate.txt
│   └── worker-d/
│       ├── main.py
│       ├── llm_client.py
│       └── config/prompt_finalize.txt
└── redis/
    └── redis.conf
```

**Execution Flow:**
```
Client → Master (/task)
Master → A → B → C → [check D availability]
If Worker-D registered → Execute D → Aggregate Result
```

---

### 3. LLM Provider Abstraction (Gemini / Bedrock / Mock)

**File:** `llm_client.py`
```python
import os, json, boto3, google.generativeai as genai

class LLMClient:
    def __init__(self, provider="gemini"):
        self.provider = provider
        if provider == "gemini":
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        elif provider == "bedrock":
            self.client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION"))

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.provider == "gemini":
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content([system_prompt, user_prompt])
            return response.text

        elif self.provider == "bedrock":
            body = json.dumps({"inputText": user_prompt, "system": system_prompt})
            response = self.client.invoke_model(modelId="amazon.nova-pro-v1:0", body=body)
            return json.loads(response["body"].read())["outputText"]

        else:
            return f"Simulated LLM output for: {user_prompt}"
```

---

### 4. Worker Roles & System Prompts

| Worker | Role | System Prompt Purpose | Example Prompt |
|---------|------|------------------------|----------------|
| **A** | Analyzer | Parse user objective and extract intent | “You are an intent extraction agent. Identify what the user wants to eat and their preferences.” |
| **B** | Retriever | Query known restaurant or menu data | “Search for candidate restaurants that match taste and budget.” |
| **C** | Evaluator | Rank and justify results | “Evaluate retrieved results and select top matches with reasoning.” |
| **D** | Finalizer (Hot-Pluggable) | Generate natural summary output | “Generate a friendly recommendation summary for the user.” |

---

### 5. Worker-D Hot Plugging Logic

**Dispatcher Behavior:**
```python
def check_for_extension():
    registry = redis.hgetall("routing")
    for agent, meta in registry.items():
        if "finalize" in meta["capabilities"]:
            return meta["url"]
    return None
```

When Worker-D joins the network, it registers with:
```json
{
  "agent_id": "worker-d",
  "capabilities": ["finalize"],
  "url": "http://worker-d:5004"
}
```
The Master automatically extends the pipeline to include D in the next task cycle.

---

### 6. Docker Compose (Local Gemini Mode)

```yaml
version: '3'
services:
  redis:
    image: redis:7
    ports: ["6379:6379"]

  llm-gateway:
    build: ./llm-gateway
    ports: ["7000:7000"]
    environment:
      - LLM_PROVIDER=gemini
      - GEMINI_API_KEY=${GEMINI_API_KEY}

  master-agent:
    build: ./master-agent
    ports: ["8000:8000"]
    environment:
      - REDIS_HOST=redis
      - MASTER_MODE=pipeline
      - LLM_GATEWAY_URL=http://llm-gateway:7000
    depends_on: [redis, llm-gateway]

  worker-a:
    build: ./agents/worker-a
    environment:
      - REDIS_HOST=redis
      - LLM_GATEWAY_URL=http://llm-gateway:7000
      - AGENT_ID=worker-a

  worker-b:
    build: ./agents/worker-b
    environment:
      - REDIS_HOST=redis
      - LLM_GATEWAY_URL=http://llm-gateway:7000
      - AGENT_ID=worker-b

  worker-c:
    build: ./agents/worker-c
    environment:
      - REDIS_HOST=redis
      - LLM_GATEWAY_URL=http://llm-gateway:7000
      - AGENT_ID=worker-c

  worker-d:
    build: ./agents/worker-d
    environment:
      - REDIS_HOST=redis
      - LLM_GATEWAY_URL=http://llm-gateway:7000
      - AGENT_ID=worker-d
```

---

### 7. Local Testing Workflow

| Step | Command / Action | Validation |
|------|------------------|-------------|
| 1️⃣ | `docker compose up --build` | Ensure all containers online and registered in Redis |
| 2️⃣ | `curl -X POST localhost:8000/task -d '{"objective": "幫我推薦一家辣味餐廳"}' -H 'Content-Type: application/json'` | Verify sequential flow A→B→C→(D if available) |
| 3️⃣ | Check `worker-*` logs | Confirm each worker received correct subtask |
| 4️⃣ | `docker stop worker-d` | Simulate unplug, Master skips finalize stage |
| 5️⃣ | `docker start worker-d` | Auto rejoin → pipeline extended again |

---

### 8. Acceptance Criteria

- ✅ Master correctly decomposes and routes tasks.
- ✅ Workers execute sequentially, with Redis synchronization.
- ✅ Gemini LLM responses are received and passed downstream.
- ✅ Worker-D dynamically joins or leaves without restarting other containers.
- ✅ Same codebase supports `LLM_PROVIDER=bedrock` after migration.

---

### 9. Next Phase: AWS Deployment Plan (Summary)

| Component | AWS Equivalent | Note |
|------------|----------------|------|
| Docker containers | Amazon ECS Fargate | Each worker as task definition |
| Redis | ElastiCache for Redis | Shared memory and routing table |
| LLM Provider | Bedrock (Nova / Claude) | Replace Gemini with SDK call |
| Logs | CloudWatch Logs | Each container outputs via driver |
| Config & Secrets | Secrets Manager | API keys, region, role policies |

This specification ensures local validation with Gemini before full AWS Bedrock deployment.
