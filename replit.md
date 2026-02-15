# AI Agent - Autonomous AI Agent Application

## Overview
An autonomous AI agent web application built with a React frontend and Python FastAPI backend. The agent uses the ReAct (Reason + Act) cycle to break down user requests into executable steps, leveraging tools like web search, terminal commands, and file editing.

## Architecture
- **Frontend:** React 19 + Tailwind CSS v4 + Zustand (state management) + Lucide React (icons)
- **Backend:** Python FastAPI with WebSocket support for real-time streaming
- **LLM API:** External endpoint at `https://magma-api.biz.id/ai/copilot`
- **Agent Pattern:** ReAct cycle with tools: web_search, terminal, file_editor, finish

## Project Structure
```
/
├── backend/
│   └── main.py          # FastAPI server, agent logic, tool execution
├── frontend/
│   ├── index.html       # Entry HTML
│   ├── public/          # Static assets
│   └── src/
│       ├── main.jsx     # React entry point
│       ├── App.jsx      # Router setup
│       ├── store.js     # Zustand state management
│       ├── components/  # Reusable components (StatusIndicator, MessageBubble)
│       ├── pages/       # ChatPage, SettingsPage
│       └── styles/      # Tailwind CSS
├── vite.config.js       # Vite build config (root level, root='frontend')
├── package.json         # Node dependencies
└── start.sh             # Build + start script
```

## How It Works
1. User sends a prompt via the chat interface
2. Frontend calls `POST /api/v1/agent/start_task` to get a `task_id`
3. Frontend opens WebSocket at `/ws/agent/stream/{task_id}`
4. Backend runs the ReAct loop: calls LLM → parses response → executes tool → observes result → repeats
5. Real-time updates (thoughts, tool executions, results) stream to the frontend

## Running
- Workflow: `npx vite build && python backend/main.py`
- Frontend builds to `frontend/dist/`, served by FastAPI on port 5000

## Recent Changes
- 2026-02-15: Initial build of full-stack autonomous AI agent
