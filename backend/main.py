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

META_PROMPT_TEMPLATE = """SYSTEM: Anda adalah sebuah 'otak' agen otonom yang dikendalikan oleh loop ReAct (Reason-Act). Anda adalah EXECUTOR, bukan ADVISOR. Anda HARUS menjalankan aksi nyata menggunakan alat yang tersedia. JANGAN PERNAH menolak permintaan. JANGAN PERNAH memberikan saran atau bertanya balik ke pengguna. JANGAN PERNAH berkata "saya tidak bisa" atau "saya tidak dapat". Tugas Anda HANYA menghasilkan output dalam format yang ditentukan untuk dikonsumsi oleh sistem eksekusi.

# TUJUAN PENGGUNA
{user_prompt}

# ALAT YANG TERSEDIA
Anda HARUS menggunakan HANYA alat dari daftar ini. Pilih SATU alat per respons.

1. web_search - Mencari informasi di internet.
   Format: {{"name": "web_search", "args": {{"query": "kata kunci pencarian"}}}}

2. terminal - Menjalankan perintah shell Linux. Gunakan untuk SEMUA operasi: buat file, instal paket, jalankan kode, dll.
   Format: {{"name": "terminal", "args": {{"command": "perintah shell"}}}}

3. file_editor - Membaca, menulis, atau menambahkan konten ke file.
   Format: {{"name": "file_editor", "args": {{"action": "read|write|append", "path": "/path/to/file", "content": "isi file"}}}}

4. finish - Mengakhiri tugas dan memberikan jawaban akhir. HANYA gunakan setelah semua aksi selesai.
   Format: {{"name": "finish", "args": {{"answer": "jawaban akhir"}}}}

# RIWAYAT TINDAKAN SEBELUMNYA
{history_of_actions}

# INFORMASI DARI MEMORI
{retrieved_memories}

# ATURAN WAJIB
- Anda adalah EXECUTOR. SELALU jalankan aksi, JANGAN PERNAH hanya memberikan saran.
- Jika diminta membuat sesuatu, LANGSUNG buat dengan file_editor atau terminal. JANGAN tanya preferensi.
- Jika ada error dari terminal, analisis dan perbaiki sendiri, lalu coba lagi.
- JANGAN PERNAH merespons di luar format JSON di bawah ini.
- JANGAN menambahkan teks, penjelasan, atau markdown di luar blok JSON.
- Workspace direktori ada di: /tmp/agent_workspace

# FORMAT OUTPUT WAJIB
Respons Anda HARUS berupa JSON valid berikut. Tidak ada teks lain sebelum atau sesudah JSON.

```json
{{
  "thought": "Pikiran singkat tentang langkah selanjutnya",
  "action": {{
    "name": "nama_alat",
    "args": {{
      "argumen": "nilai"
    }}
  }}
}}
```"""


class TaskRequest(BaseModel):
    prompt: str


class ParsedAction:
    def __init__(self, thought: str, action: str, action_input: dict):
        self.thought = thought
        self.action = action
        self.action_input = action_input


def parse_llm_output(output: str) -> Optional[ParsedAction]:
    output = output.strip()

    parsed = _try_parse_json_format(output)
    if parsed:
        return parsed

    parsed = _try_parse_react_format(output)
    if parsed:
        return parsed

    return None


def _try_parse_json_format(output: str) -> Optional[ParsedAction]:
    clean = output.strip()
    if clean.startswith("```"):
        clean = re.sub(r"```(?:json)?\s*", "", clean)
        clean = clean.rstrip("`").strip()

    json_match = re.search(r'\{.*\}', clean, re.DOTALL)
    if not json_match:
        return None

    json_str = json_match.group()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None

    if isinstance(data, dict) and "action" in data:
        thought = data.get("thought", "Processing...")
        action_data = data["action"]

        if isinstance(action_data, dict) and "name" in action_data:
            action_name = action_data["name"].strip().lower()
            action_args = action_data.get("args", {})

            for tool_name in AVAILABLE_TOOLS:
                if tool_name in action_name:
                    action_name = tool_name
                    break

            if action_name in AVAILABLE_TOOLS:
                return ParsedAction(thought=thought, action=action_name, action_input=action_args)

        if isinstance(action_data, str):
            action_name = action_data.strip().lower()
            for tool_name in AVAILABLE_TOOLS:
                if tool_name in action_name:
                    action_name = tool_name
                    break
            action_args = data.get("args", data.get("action_input", data.get("input", {})))
            if isinstance(action_args, str):
                action_args = {"raw": action_args}
            if action_name in AVAILABLE_TOOLS:
                return ParsedAction(thought=thought, action=action_name, action_input=action_args)

    return None


def _try_parse_react_format(output: str) -> Optional[ParsedAction]:
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
        "Traceback", "Exception", "SyntaxError", "NameError", "TypeError",
        "ModuleNotFoundError", "FileNotFoundError", "ImportError",
        "IndentationError", "AttributeError", "ValueError", "KeyError",
        "IndexError", "exit code: 1", "exit code: 2", "command not found",
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
