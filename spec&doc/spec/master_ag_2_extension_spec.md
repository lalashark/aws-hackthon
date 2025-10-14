## Master AG2 Extension Spec v0.2  
(Scope: Task Decomposition + Adaptive Routing)

### 1. Objective
Enable the Master to intelligently understand task content, decompose it into subtasks, and route each subtask to the most suitable sub agent based on declared capabilities. AG2 serves as the decision layer, not as the communication or transport layer.

---

### 2. Task Decomposition Module (AG2-Decomposer)

**Function Definition**  
- Function name: `decompose_task()`  
- Trigger: Invoked when `/task` is received by Master Dispatcher.  
- Input: `task_id`, `objective` (natural language), `available_caps` (from routing.py).  
- Output: Structured list of subtasks.

**Example Output:**
```json
{
  "task_id": "T-001",
  "objective": "Analyze customer feedback and summarize main complaints.",
  "subtasks": [
    {
      "sub_id": "T-001-A",
      "command": "analyze",
      "description": "Extract negative sentiment patterns from feedback data"
    },
    {
      "sub_id": "T-001-B",
      "command": "summarize",
      "description": "Summarize the extracted results into 3 bullet points"
    }
  ]
}
```

**Implementation Logic (Spec Level)**  
1. AG2 agent `MasterDecomposer` receives the `objective`.  
2. Retrieves all available capabilities from `routing.py`.  
3. Generates structured JSON mapping each subtask to a capability.  
4. Returns structured subtasks to the dispatcher for assignment.

**Module Interaction**
| Source | Output | Receiver |
|---------|---------|-----------|
| dispatcher.py | objective | ag2_decomposer.py |
| ag2_decomposer.py | subtasks | dispatcher.py |
| routing.py | available_caps | ag2_decomposer.py |

---

### 3. Adaptive Routing Module (AG2-Router)

**Function Definition**  
- Function name: `decide_route()`  
- Trigger: Called before each subtask dispatch.  
- Input: `command`, `candidates` (agents capable of executing the command), `context` (task state).  
- Output: Selected agent id and reasoning.

**Input Example:**
```json
{
  "command": "analyze",
  "candidates": [
    {"id": "worker-a", "caps": ["summarize", "analyze"], "load": 0.2},
    {"id": "worker-b", "caps": ["analyze"], "load": 0.1}
  ],
  "context": {
    "task_id": "T-001",
    "recent_failures": {"worker-a": 1, "worker-b": 0}
  }
}
```

**Output Example:**
```json
{
  "selected": "worker-b",
  "reason": "Has lowest current load and fewer recent failures."
}
```

**Implementation Logic (Spec Level)**  
1. Retrieve all candidate agents for the command.  
2. Collect each agent's metrics (latency, failure rate, load).  
3. AG2 agent `AdaptiveRouterAgent` reasons about the best fit.  
4. Returns `selected` agent and explanation.  
5. Dispatcher executes dispatch and logs reasoning.

**Module Interaction**
```
Dispatcher → AG2Router.decide_route(command, candidates)
           → returns best agent_id
           → Dispatcher dispatches via HTTP POST
```

---

### 4. Module and File Layout
```
master-agent/
├── ag2_controller/
│   ├── __init__.py
│   ├── decomposer.py       # Task Decomposition via AG2
│   └── adaptive_router.py  # Adaptive Routing via AG2
├── routing.py
├── dispatcher.py
└── main.py
```

**Controller Interface**
```python
class AG2Controller:
    def decompose_task(self, objective: str, caps: list) -> list:
        """Return list of subtasks with command assignments."""
    def decide_route(self, command: str, candidates: list, context: dict) -> dict:
        """Return selected agent and reasoning."""
```

---

### 5. Execution Flow Overview
```
Client → POST /task {objective: "..."}
   ↓
Master Dispatcher
   ↓ calls → AG2Decomposer.decompose_task()
   ↓ produces subtasks [A, B]
   ↓ for each subtask:
         calls → AG2Router.decide_route()
         ↓
         dispatches to selected worker
   ↓
Workers → POST /result
   ↓
Master aggregates + logs reasoning chain
```

---

### 6. Summary Table
| Module | Function | Input | Output | Uses AG2 |
|---------|-----------|--------|----------|-----------|
| ag2_decomposer.py | Automatic task decomposition | objective, capabilities | subtasks[] | Yes |
| ag2_router.py | Intelligent routing | command, candidates, context | selected agent | Yes |
| dispatcher.py | Task dispatch | subtasks | result events | Partial |
| routing.py | Capability index | agent_id, capabilities | candidates | No |
| memory.py | Redis access | keys | values | No |

