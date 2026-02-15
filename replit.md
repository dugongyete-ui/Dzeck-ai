# AI Agent - Autonomous AI Agent Application

## Overview
An autonomous AI agent web application built with a React frontend and Python FastAPI backend. The agent uses the ReAct (Reason + Act) cycle to break down user requests into executable steps, leveraging tools like web search, terminal commands, and file editing. Includes long-term memory, self-correction capabilities, and professional streaming UI.

## Architecture
- **Frontend:** React 19 + Tailwind CSS v4 + Zustand (state management) + Lucide React (icons)
- **Backend:** Python FastAPI with WebSocket support for real-time streaming
- **LLM API:** External endpoint at `https://magma-api.biz.id/ai/copilot`
- **Agent Pattern:** ReAct cycle with tools: web_search, terminal, file_editor, finish
- **Memory:** JSON-based long-term memory with keyword-matching retrieval
- **Self-Correction:** Automatic error detection and retry logic (max 3 retries per error)

## Project Structure
```
/
├── backend/
│   ├── main.py            # FastAPI server, ReAct loop, WebSocket streaming, self-correction logic
│   ├── tool_executor.py   # Tool functions + dispatcher with argument normalization
│   └── memory_manager.py  # Long-term memory: save/retrieve memories across sessions
├── frontend/
│   ├── index.html         # Entry HTML
│   ├── public/            # Static assets
│   └── src/
│       ├── main.jsx       # React entry point
│       ├── App.jsx        # Router setup
│       ├── store.js       # Zustand state management
│       ├── components/    # StatusIndicator, MessageBubble (with self-correction UI)
│       ├── pages/         # ChatPage, SettingsPage
│       └── styles/        # Tailwind CSS with animations
├── vite.config.js         # Vite build config (root level, root='frontend')
├── package.json           # Node dependencies
└── pyproject.toml         # Python dependencies
```

## Key Features
1. **ReAct Loop:** Iterative reasoning and action cycle with up to 20 steps
2. **Self-Correction:** Detects errors in tool outputs, automatically retries with fixes
3. **Streaming UI:** Real-time WebSocket messages for thoughts, tool execution, outputs, and self-correction
4. **Long-term Memory:** Saves task results and search results for future context
5. **Professional UI:** Animated message bubbles, step indicators, retry counters, error highlighting

## WebSocket Message Types
- `status`: Step progress updates
- `thought`: Agent's reasoning (purple, with brain icon)
- `tool_start`: Tool execution start (orange, with tool icon)
- `tool_output`: Tool results (with error detection highlighting)
- `self_correction`: Retry attempt notification (amber, with refresh icon)
- `final_answer`: Completed result (green, with step/retry summary)
- `error`: Error messages (red)

## How It Works
1. User sends a prompt via the chat interface
2. Frontend calls `POST /api/v1/agent/start_task` to get a `task_id`
3. Frontend opens WebSocket at `/ws/agent/stream/{task_id}`
4. Backend retrieves relevant memories from long-term storage
5. Backend runs the ReAct loop: calls LLM → parses response → executes tool → observes result → repeats
6. If a tool (especially terminal) produces an error, the agent detects it and enters self-correction mode
7. Self-correction: analyzes error → fixes code/command → retries (up to 3 attempts per error)
8. Tool results and search outputs are saved to memory for future context
9. Real-time updates stream to the frontend with step numbers and retry counts

## Running
- Workflow: `npx --yes vite build && python backend/main.py`
- Frontend builds to `frontend/dist/`, served by FastAPI on port 5000
- Quick setup: `bash setup.sh` (installs all Node.js + Python deps and builds frontend)

## Multi-User Safety
- **Workspace Isolation:** Each task gets its own directory at `/tmp/agent_workspaces/{task_id[:12]}/`
- **Memory Separation:** Each session has its own memory file at `/tmp/agent_memories/{session_id}.json`
- **Rate Limiting:** Max 20 API calls per 60 seconds, max 10 concurrent tasks
- **Auto Cleanup:** Workspaces deleted 5 minutes after task completion, memory files cleaned after 24 hours
- **Thread Safety:** Threading locks on memory file read/write operations

## Recent Changes
- 2026-02-15: Added setup.sh auto-download dependencies script for quick project setup
- 2026-02-15: Multi-user safety - isolated workspaces per task, separated memory per session, rate limiting (20 calls/60s, 10 max concurrent), auto-cleanup of expired tasks/workspaces
- 2026-02-15: Added dual parser (JSON format + ReAct fallback) for robust LLM output handling
- 2026-02-15: Upgraded UI/UX - gradient branding, mobile-responsive, backdrop blur, smooth animations
- 2026-02-15: Enhanced UI with animations, step indicators, error highlighting, retry counters
- 2026-02-15: Added self-correction & recursive debugging (error detection, retry logic)
- 2026-02-15: Added long-term memory system (memory_manager.py) with keyword retrieval
- 2026-02-15: Initial build of full-stack autonomous AI agent
