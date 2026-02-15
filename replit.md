# AI Agent - Autonomous AI Agent Application

## Overview
An autonomous AI agent web application built with a React frontend and Python FastAPI backend. The agent uses the ReAct (Reason + Act) cycle to break down user requests into executable steps, leveraging tools like web search, terminal commands, and file editing. Includes long-term memory for cross-session context.

## Architecture
- **Frontend:** React 19 + Tailwind CSS v4 + Zustand (state management) + Lucide React (icons)
- **Backend:** Python FastAPI with WebSocket support for real-time streaming
- **LLM API:** External endpoint at `https://magma-api.biz.id/ai/copilot`
- **Agent Pattern:** ReAct cycle with tools: web_search, terminal, file_editor, finish
- **Memory:** JSON-based long-term memory with keyword-matching retrieval

## Project Structure
```
/
├── backend/
│   ├── main.py            # FastAPI server, ReAct loop, WebSocket streaming
│   ├── tool_executor.py   # Tool functions + dispatcher with argument normalization
│   └── memory_manager.py  # Long-term memory: save/retrieve memories across sessions
├── frontend/
│   ├── index.html         # Entry HTML
│   ├── public/            # Static assets
│   └── src/
│       ├── main.jsx       # React entry point
│       ├── App.jsx        # Router setup
│       ├── store.js       # Zustand state management
│       ├── components/    # Reusable components (StatusIndicator, MessageBubble)
│       ├── pages/         # ChatPage, SettingsPage
│       └── styles/        # Tailwind CSS
├── vite.config.js         # Vite build config (root level, root='frontend')
├── package.json           # Node dependencies
└── start.sh               # Build + start script
```

## How It Works
1. User sends a prompt via the chat interface
2. Frontend calls `POST /api/v1/agent/start_task` to get a `task_id`
3. Frontend opens WebSocket at `/ws/agent/stream/{task_id}`
4. Backend retrieves relevant memories from long-term storage
5. Backend runs the ReAct loop: calls LLM → parses response → executes tool → observes result → repeats
6. Tool results and search outputs are saved to memory for future context
7. Real-time updates (thoughts, tool executions, results) stream to the frontend

## Running
- Workflow: `./node_modules/.bin/vite build && python backend/main.py`
- Frontend builds to `frontend/dist/`, served by FastAPI on port 5000

## Recent Changes
- 2026-02-15: Added long-term memory system (memory_manager.py) with keyword retrieval
- 2026-02-15: Improved tool argument normalization and robust JSON parsing
- 2026-02-15: Refactored tool execution into separate `tool_executor.py` module with dispatcher pattern
- 2026-02-15: Initial build of full-stack autonomous AI agent
