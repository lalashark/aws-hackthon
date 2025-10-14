## Redis Container Specification v0.1

### 1. Objective
Define the Redis-based memory and coordination layer used by the Master Agent and all Sub Agents (worker-a, worker-b, worker-c) in the AG2 PoC architecture. Redis acts as the shared state, communication, and context backbone for the entire system.

---

### 2. Role in the Architecture
| Function | Description |
|-----------|-------------|
| Shared Memory | Stores task context, routing tables, and agent states. |
| Coordination Layer | Manages task results, agent registration, and event signaling. |
| Communication Hub | Enables asynchronous communication via Pub/Sub or Streams. |

---

### 3. Data Structures
| Key | Type | Description |
|------|------|-------------|
| `routing` | Hash | Maps `agent_id` → metadata `{url, capabilities}` |
| `cap_index:<cap>` | Set | Stores all agents supporting a given capability |
| `heartbeat:<agent>` | Key | Liveness indicator (TTL 30s) |
| `memory:<agent>` | List | Local message log for debugging |
| `results:<task_id>` | List | Stores results for each task processed by Sub Agents |
| `global:context` | Hash | Global task context shared across agents |
| `agent_events` | Pub/Sub Channel | Used for dynamic agent registration/removal |
| `ag2:trace:<task_id>:<agent>` | List | Persists AG2 reasoning traces emitted by worker runtimes |

---

### 4. Core Responsibilities
| Category | Purpose | Used By |
|-----------|----------|----------|
| Routing Table | Keep track of all active agents and their capabilities | Master |
| Capability Index | Reverse lookup for task assignment | Master |
| Shared Context | Global information accessible to all agents | Master + Sub |
| Task Results | Aggregated outputs per task | Master |
| Heartbeat Tracking | Health monitoring of Sub Agents | Master + Sub |
| Event Messaging | Dynamic updates (join/leave events) | Master + Sub |
| AG2 Trace Store | Persist worker reasoning traces for auditability | Master + Observability tools |

---

### 5. Container Configuration
| Parameter | Value | Description |
|------------|--------|-------------|
| **Image** | `redis:7.2-alpine` | Lightweight production-ready Redis image |
| **Container Name** | `redis` | Shared memory container |
| **Port** | `6379` | Default Redis port |
| **Volume** | `/data` | Optional persistence layer |
| **Network** | `agnet` | Shared internal network with all agents |
| **Command** | `redis-server --appendonly yes` | Enables append-only persistence |
| **Authentication** | Optional via `requirepass` | Add during cloud deployment |

---

### 6. docker-compose Configuration
```yaml
version: '3'
services:
  redis:
    image: redis:7.2-alpine
    container_name: redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: ["redis-server", "--appendonly", "yes"]
    networks:
      - agnet

  master-agent:
    build: ./master
    depends_on:
      - redis
    networks:
      - agnet

  worker-a:
    build: ./agents/worker-a
    depends_on:
      - redis
    networks:
      - agnet

  worker-b:
    build: ./agents/worker-b
    depends_on:
      - redis
    networks:
      - agnet

  worker-c:
    build: ./agents/worker-c
    depends_on:
      - redis
    networks:
      - agnet

networks:
  agnet:

volumes:
  redis_data:
```

---

### 7. Communication Overview
```
Master ↔ Redis  → routing, task context, results, AG2 traces
Sub Agents ↔ Redis  → heartbeat, global context, AG2 traces, event channel
Redis Pub/Sub  → dynamic registration and coordination
```

---

### 8. Redis Interface Abstraction (for AG2 Integration)
```python
class MemoryAdapter:
    def set_context(self, key, value): ...
    def get_context(self, key): ...
    def publish_event(self, channel, message): ...
    def subscribe(self, channel): ...
    def record_result(self, task_id, result): ...
    def get_results(self, task_id): ...
```

This abstraction will allow AG2 to replace Redis with other backends (e.g., DynamoDB, Firestore, or ElastiCache) without modifying higher-level orchestration code.

---

### 9. Future Enhancements
| Feature | Description |
|----------|-------------|
| Multi-Namespace Context | Use `namespace:task_id` for isolated memory scopes. |
| Stream-based Messaging | Replace Pub/Sub with Redis Streams for task persistence. |
| Persistent Context Layer | Introduce RDB snapshot or MongoDB for long-term storage. |
| Secure Deployment | Enable TLS and IAM-based credentials in cloud environments. |

---

### 10. Summary
- Redis serves as both shared memory and coordination bus for all agents.
- Supports routing, heartbeat, results aggregation, AG2 trace persistence, and global context management.
- Current PoC uses ephemeral storage; can migrate to AWS ElastiCache in production.
- Future AG2 integration will abstract Redis through a MemoryAdapter API for pluggable backends.
