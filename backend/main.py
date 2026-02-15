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
from memory_manager import retrieve_memories, save_task_result, save_search_result

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks = {}

META_PROMPT_TEMPLATE = """Anda adalah agen AI otonom yang ahli. Misi Anda adalah untuk menyelesaikan permintaan pengguna dengan memecahnya menjadi langkah-langkah yang dapat dieksekusi.

Tujuan Utama: {user_prompt}

Informasi Relevan dari Memori:
{retrieved_memories}

Riwayat Tindakan Sejauh Ini:
{history_of_actions}

Anda memiliki akses ke alat-alat berikut:

---
Tool: web_search
Deskripsi: Gunakan untuk mencari informasi terkini di internet.
Argumen: {{"query": "pertanyaan atau kata kunci pencarian"}}

Tool: terminal
Deskripsi: Gunakan untuk menjalankan perintah shell di lingkungan Linux. Penting untuk manajemen file, instalasi, dan eksekusi skrip.
Argumen: {{"command": "perintah yang akan dieksekusi"}}

Tool: file_editor
Deskripsi: Gunakan untuk menulis, membaca, atau memodifikasi file.
Argumen: {{"action": "read|write|append", "path": "/path/to/file", "content": "isi file (hanya untuk write/append)"}}

Tool: finish
Deskripsi: Gunakan alat ini ketika Anda yakin tugas telah selesai sepenuhnya.
Argumen: {{"answer": "jawaban akhir atau ringkasan hasil untuk pengguna"}}
---

SELF-CORRECTION (PERBAIKAN DIRI):
Jika sebuah alat, terutama 'terminal', menghasilkan error (misalnya SyntaxError, ModuleNotFoundError, FileNotFoundError, atau pesan error lainnya di STDERR), tugas Anda BELUM selesai. Anda HARUS:
1. Analisis pesan error dengan cermat.
2. Tentukan penyebab error (misalnya: typo, modul belum terinstal, path salah, sintaks salah).
3. Gunakan alat yang sesuai untuk memperbaiki masalah (misalnya 'file_editor' untuk memperbaiki kode, atau 'terminal' untuk menginstal dependensi).
4. Jalankan kembali perintah yang gagal untuk memverifikasi perbaikan.
5. Ulangi proses ini hingga perintah berhasil atau Anda yakin tidak dapat memperbaikinya (maksimal 3 percobaan perbaikan per error).
JANGAN PERNAH menganggap tugas selesai jika output terakhir mengandung error. Selalu coba perbaiki terlebih dahulu.

PENTING: Anda HARUS menjawab HANYA dalam format berikut. JANGAN tambahkan penjelasan lain di luar format ini:

Thought: [Pikiran Anda di sini, jelaskan rencana Anda dalam satu kalimat]
Action: [Nama alat PERSIS salah satu dari: web_search, terminal, file_editor, finish]
Action Input: [Argumen dalam format JSON yang valid]"""


class TaskRequest(BaseModel):
    prompt: str


class ParsedAction:
    def __init__(self, thought: str, action: str, action_input: dict):
        self.thought = thought
        self.action = action
        self.action_input = action_input


def parse_llm_output(output: str) -> Optional[ParsedAction]:
    output = output.strip()

    thought_match = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
    action_match = re.search(r"Action:\s*(.+?)(?:\n|$)", output)
    action_input_match = re.search(r"Action Input:\s*(.+)", output, re.DOTALL)

    if not action_match:
        for tool_name in AVAILABLE_TOOLS:
            if tool_name in output.lower():
                action_match = type('Match', (), {'group': lambda self, x: tool_name})()
                break

    if not action_match or not action_input_match:
        return None

    thought = thought_match.group(1).strip() if thought_match else "Processing..."
    action = action_match.group(1).strip().lower()

    for tool_name in AVAILABLE_TOOLS:
        if tool_name in action:
            action = tool_name
            break

    raw_input = action_input_match.group(1).strip()

    action_input = _parse_json_input(raw_input)

    return ParsedAction(thought=thought, action=action, action_input=action_input)


def _parse_json_input(raw_input: str) -> dict:
    raw_input = raw_input.strip()
    if raw_input.startswith("```"):
        raw_input = re.sub(r"```(?:json)?\s*", "", raw_input)
        raw_input = raw_input.rstrip("`").strip()

    try:
        return json.loads(raw_input)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'\{[^{}]*\}', raw_input, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    json_match = re.search(r'\{.*\}', raw_input, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {"raw": raw_input}


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


def call_llm(user_prompt: str, history: str, memories: str = ""):
    full_prompt = META_PROMPT_TEMPLATE.format(
        user_prompt=user_prompt,
        history_of_actions=history if history else "Belum ada tindakan.",
        retrieved_memories=memories if memories else "Tidak ada memori sebelumnya."
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
    max_iterations = 20
    error_patterns = [
        "error", "Error", "ERROR", "Traceback", "Exception",
        "SyntaxError", "NameError", "TypeError", "ModuleNotFoundError",
        "FileNotFoundError", "ImportError", "IndentationError",
        "AttributeError", "ValueError", "KeyError", "IndexError",
        "exit code: 1", "exit code: 2", "command not found",
        "Permission denied", "No such file",
    ]
    retry_count = 0
    max_retries_per_error = 3
    last_failed_command = None

    try:
        memories = await asyncio.to_thread(retrieve_memories, user_prompt)

        for i in range(max_iterations):
            history_str = "\n".join(history_lines) if history_lines else ""

            await websocket.send_json({
                "type": "status",
                "step": i + 1,
                "total_steps": max_iterations,
                "content": f"Thinking... (step {i+1})"
            })

            parsed, raw_output = await asyncio.to_thread(
                call_llm, user_prompt, history_str, memories
            )

            if parsed is None:
                if raw_output and len(raw_output) > 10:
                    await websocket.send_json({
                        "type": "thought",
                        "content": raw_output[:500] if raw_output else "Could not parse LLM response."
                    })
                await websocket.send_json({
                    "type": "final_answer",
                    "content": raw_output if raw_output and len(raw_output) > 10 else "I encountered an issue processing this request. Please try again."
                })
                break

            await websocket.send_json({
                "type": "thought",
                "step": i + 1,
                "content": parsed.thought
            })

            if parsed.action == "finish":
                answer = parsed.action_input.get("answer", parsed.action_input.get("raw", "Task completed."))
                await websocket.send_json({
                    "type": "final_answer",
                    "content": answer,
                    "steps_taken": i + 1,
                    "retries": retry_count,
                })
                await asyncio.to_thread(
                    save_task_result, user_prompt, answer, "finish"
                )
                task["status"] = "completed"
                break

            await websocket.send_json({
                "type": "tool_start",
                "step": i + 1,
                "tool_name": parsed.action,
                "args": json.dumps(parsed.action_input, ensure_ascii=False)
            })

            tool_output = await asyncio.to_thread(
                execute_tool, parsed.action, parsed.action_input
            )

            has_error = any(pat in tool_output for pat in error_patterns)

            if has_error and parsed.action == "terminal":
                retry_count += 1
                is_same_error = (last_failed_command == json.dumps(parsed.action_input))
                same_error_retries = retry_count if is_same_error else 1
                last_failed_command = json.dumps(parsed.action_input)

                if same_error_retries <= max_retries_per_error:
                    await websocket.send_json({
                        "type": "self_correction",
                        "step": i + 1,
                        "retry_attempt": same_error_retries,
                        "max_retries": max_retries_per_error,
                        "error_snippet": tool_output[:300],
                        "content": f"Error detected. Attempting self-correction (attempt {same_error_retries}/{max_retries_per_error})..."
                    })
                else:
                    await websocket.send_json({
                        "type": "self_correction",
                        "step": i + 1,
                        "retry_attempt": same_error_retries,
                        "max_retries": max_retries_per_error,
                        "content": f"Max retries reached for this error. Moving on..."
                    })
                    last_failed_command = None
                    retry_count = 0
            else:
                last_failed_command = None

            if parsed.action == "web_search":
                query = parsed.action_input.get("query", parsed.action_input.get("raw", ""))
                await asyncio.to_thread(save_search_result, query, tool_output[:300])

            await websocket.send_json({
                "type": "tool_output",
                "step": i + 1,
                "tool_name": parsed.action,
                "has_error": has_error,
                "output": tool_output[:2000]
            })

            history_lines.append(f"Step {i+1}:")
            history_lines.append(f"  Thought: {parsed.thought}")
            history_lines.append(f"  Action: {parsed.action}")
            history_lines.append(f"  Action Input: {json.dumps(parsed.action_input, ensure_ascii=False)}")
            history_lines.append(f"  Observation: {tool_output[:500]}")
            if has_error:
                history_lines.append(f"  STATUS: ERROR DETECTED - self-correction needed")
            history_lines.append("")

            await asyncio.sleep(0.5)
        else:
            await websocket.send_json({
                "type": "final_answer",
                "content": "Maximum iterations reached. Here's what I accomplished so far based on the steps above.",
                "steps_taken": max_iterations,
                "retries": retry_count,
            })
            task["status"] = "max_iterations"

    except WebSocketDisconnect:
        task["status"] = "disconnected"
    except Exception as e:
        print(f"[WS] Error in stream_task: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"An error occurred: {str(e)}"
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
