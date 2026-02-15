import asyncio
import json
import os
import re
import uuid
import urllib.parse
from typing import Optional

import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from tool_executor import execute_tool, AVAILABLE_TOOLS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks = {}

tool_descriptions = "\n".join([
    "Tool: web_search",
    'Deskripsi: Gunakan untuk mencari informasi terkini di internet.',
    'Argumen: {"query": "pertanyaan atau kata kunci pencarian"}',
    "",
    "Tool: terminal",
    'Deskripsi: Gunakan untuk menjalankan perintah shell di lingkungan Linux. Penting untuk manajemen file, instalasi, dan eksekusi skrip.',
    'Argumen: {"command": "perintah yang akan dieksekusi"}',
    "",
    "Tool: file_editor",
    'Deskripsi: Gunakan untuk menulis, membaca, atau memodifikasi file.',
    'Argumen: {"action": "read|write|append", "path": "/path/to/file", "content": "isi file (hanya untuk write/append)"}',
    "",
    "Tool: finish",
    'Deskripsi: Gunakan alat ini ketika Anda yakin tugas telah selesai sepenuhnya.',
    'Argumen: {"answer": "jawaban akhir atau ringkasan hasil untuk pengguna"}',
])

META_PROMPT_TEMPLATE = """Anda adalah agen AI otonom yang ahli. Misi Anda adalah untuk menyelesaikan permintaan pengguna dengan memecahnya menjadi langkah-langkah yang dapat dieksekusi.

Tujuan Utama: {user_prompt}

Riwayat Tindakan Sejauh Ini:
{history_of_actions}

Anda memiliki akses ke alat-alat berikut:

---
""" + tool_descriptions + """
---

Berdasarkan Tujuan Utama dan Riwayat, tentukan langkah Anda selanjutnya.
Jawab HANYA dalam format berikut, tanpa penjelasan tambahan:

Thought: [Pikiran Anda di sini, jelaskan rencana Anda dalam satu kalimat]
Action: [Nama Alat]
Action Input: [Argumen dalam format JSON]"""


class TaskRequest(BaseModel):
    prompt: str


class ParsedAction:
    def __init__(self, thought: str, action: str, action_input: dict):
        self.thought = thought
        self.action = action
        self.action_input = action_input


def parse_llm_output(output: str) -> Optional[ParsedAction]:
    thought_match = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
    action_match = re.search(r"Action:\s*(.+?)(?:\n|$)", output)
    action_input_match = re.search(r"Action Input:\s*(.+)", output, re.DOTALL)

    if not thought_match or not action_match or not action_input_match:
        return None

    thought = thought_match.group(1).strip()
    action = action_match.group(1).strip()
    raw_input = action_input_match.group(1).strip()

    try:
        action_input = json.loads(raw_input)
    except json.JSONDecodeError:
        json_match = re.search(r'\{.*\}', raw_input, re.DOTALL)
        if json_match:
            try:
                action_input = json.loads(json_match.group())
            except json.JSONDecodeError:
                action_input = {"raw": raw_input}
        else:
            action_input = {"raw": raw_input}

    return ParsedAction(thought=thought, action=action, action_input=action_input)


def _extract_text(response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text

    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, dict):
            return result.get("response", result.get("text", json.dumps(result)))
        if isinstance(result, str):
            return result
        resp = data.get("response")
        if isinstance(resp, str):
            return resp
        return json.dumps(data)

    return str(data)


def call_llm(user_prompt: str, history: str):
    full_prompt = META_PROMPT_TEMPLATE.format(
        user_prompt=user_prompt,
        history_of_actions=history if history else "Belum ada tindakan."
    )

    encoded_prompt = urllib.parse.quote(full_prompt)
    api_url = f"https://magma-api.biz.id/ai/copilot?prompt={encoded_prompt}"

    try:
        response = requests.get(api_url, timeout=120)
        response.raise_for_status()

        llm_text = _extract_text(response)
        print(f"[LLM] Raw response: {llm_text[:500]}")

        return parse_llm_output(llm_text), llm_text
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return None, str(e)


@app.post("/api/v1/agent/start_task")
async def start_task(req: TaskRequest):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "prompt": req.prompt,
        "status": "pending",
        "history": [],
    }
    return {"task_id": task_id}


@app.websocket("/ws/agent/stream/{task_id}")
async def stream_task(websocket: WebSocket, task_id: str):
    await websocket.accept()

    if task_id not in tasks:
        await websocket.send_json({"type": "error", "content": "Task not found."})
        await websocket.close()
        return

    task = tasks[task_id]
    task["status"] = "running"
    user_prompt = task["prompt"]
    history_lines = []
    max_iterations = 15

    try:
        for i in range(max_iterations):
            history_str = "\n".join(history_lines) if history_lines else ""

            await websocket.send_json({
                "type": "status",
                "content": "Thinking..."
            })

            parsed, raw_output = await asyncio.to_thread(call_llm, user_prompt, history_str)

            if parsed is None:
                await websocket.send_json({
                    "type": "thought",
                    "content": raw_output if raw_output else "Could not parse LLM response."
                })
                await websocket.send_json({
                    "type": "final_answer",
                    "content": raw_output if raw_output else "I encountered an issue processing this request. Please try again."
                })
                break

            await websocket.send_json({
                "type": "thought",
                "content": parsed.thought
            })

            if parsed.action == "finish":
                answer = parsed.action_input.get("answer", "Task completed.")
                await websocket.send_json({
                    "type": "final_answer",
                    "content": answer
                })
                task["status"] = "completed"
                break

            await websocket.send_json({
                "type": "tool_start",
                "tool_name": parsed.action,
                "args": json.dumps(parsed.action_input)
            })

            tool_output = await asyncio.to_thread(execute_tool, parsed.action, parsed.action_input)

            await websocket.send_json({
                "type": "tool_output",
                "tool_name": parsed.action,
                "output": tool_output[:2000]
            })

            history_lines.append(f"Step {i+1}:")
            history_lines.append(f"  Thought: {parsed.thought}")
            history_lines.append(f"  Action: {parsed.action}")
            history_lines.append(f"  Action Input: {json.dumps(parsed.action_input)}")
            history_lines.append(f"  Observation: {tool_output[:500]}")
            history_lines.append("")

            await asyncio.sleep(0.5)
        else:
            await websocket.send_json({
                "type": "final_answer",
                "content": "Maximum iterations reached. Here's what I accomplished so far based on the steps above."
            })
            task["status"] = "max_iterations"

    except WebSocketDisconnect:
        task["status"] = "disconnected"
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "content": str(e)
            })
        except:
            pass
        task["status"] = "error"


STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
