## Zero-Framework Context Management
Because the project was built without heavy frameworks like LangChain or LangGraph, context management is handled through a highly efficient custom **Dual-Layer Memory System**:

# Why did I choose to work without any heavy frameworks:

The application has a small, well-defined state space, so a custom orchestrator gives more control over state correctness, token usage, latency, and failure recovery than introducing a general-purpose agent framework.
The workflow didn't need that level of orchestration.
For a larger system with many agents, persistent workflows, complex branching, human-in-the-loop execution, or distributed execution, I would reconsider using LangGraph or another orchestration framework.
And there was a lot of state management required in langgraph which gave a lot of errors earlier before and huge lines of code were written with 
lots of errors.

### 1. The Strict JSON State (Ground Truth)
Traditional chatbots blindly append massive chat transcripts together, which causes LLMs to hallucinate or forget details over time. This app instead relies on a **State Machine** backed by Redis. As the user chats and the LLM calls tools, the backend updates a strict JSON object tracking the exact progress (e.g., selected flights, passenger details). 
At the start of every single user turn, this JSON is summarized and injected directly into the **System Prompt**. The LLM never has to guess what happened 10 messages ago-it is fed the hard factual state as the ground truth before generating a single word.

### 2. The Ephemeral Tool Loop (In-Memory)
During a single turn, the LLM might need to call 3 tools in a row. How does it remember what tool it *just* called without a framework?
The orchestrator maintains an ephemeral Python list of messages strictly for the duration of the loop. Tool calls and JSON results are appended to this list and fed back to the LLM. To keep the context window small and cheap, the system throws away the messy tool-call data after the turn is over! It only saves the final User Text and Assistant Text to the long-term Redis history.

### Transactional State Rollbacks (copy.deepcopy)
Because the agent executes multiple steps in a single turn, an API rate limit or outage mid-turn could result in corrupted state (e.g., adding a passenger to the JSON but failing to book). 
The orchestrator prevents this by acting like a database transaction:
* It takes a full clone of the state at the start of the turn using Python's copy.deepcopy(state).
* A standard state.copy() is a shallow copy, meaning nested lists (like passengers) would still point to the original memory address, corrupting the backup if modified. deepcopy recursively clones every nested dictionary and list.
* If the turn crashes mid-loop, the backend instantly restores the pristine deepcopy backup, completely erasing ghost passengers or half-finished actions before the UI is updated.

### Tradeoffs of this Approach
* **Pros:** Extremely low token usage, zero hallucinations on booking state, and safe transactional rollbacks.
* **Cons:** Loss of exact tool history (the LLM cannot look back at raw JSON from 3 turns ago) and requires meticulous schema design for the JSON state object.
