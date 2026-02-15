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

PLANNER_PROMPT = """Saya sedang mengerjakan tugas berikut dan butuh bantuan langkah demi langkah.

TUGAS: {user_prompt}

{history_section}

{memory_section}

Saya bekerja di lingkungan Linux dengan akses terminal, editor file, dan pencarian web.
Direktori kerja saya: /tmp/agent_workspace

Berikan saya SATU langkah berikutnya yang harus dilakukan. Sertakan perintah terminal yang tepat, atau kode file yang perlu ditulis. Jangan berikan banyak opsi, pilihkan satu yang terbaik dan berikan perintah/kode konkret yang bisa langsung dijalankan."""

INTERPRETER_PROMPT = """Dari respons AI berikut, ekstrak SATU aksi konkret yang bisa dijalankan.

RESPONS AI:
{llm_response}

TUGAS ASLI: {user_prompt}

Berikan dalam format ini saja (tanpa teks lain):
AKSI: [terminal/file_write/file_read/web_search/selesai]
DETAIL: [perintah/path/query/jawaban]
KONTEN: [isi file jika ada]"""


class TaskRequest(BaseModel):
    prompt: str


class ParsedAction:
    def __init__(self, thought: str, action: str, action_input: dict):
        self.thought = thought
        self.action = action
        self.action_input = action_input


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


def _call_api(prompt: str) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    api_url = f"https://magma-api.biz.id/ai/copilot?prompt={encoded_prompt}"
    response = requests.get(api_url, timeout=120)
    response.raise_for_status()
    return _extract_text(response)


def _extract_code_blocks(text: str) -> list:
    blocks = []
    pattern = r'```(\w*)\n(.*?)```'
    for match in re.finditer(pattern, text, re.DOTALL):
        lang = match.group(1).lower()
        code = match.group(2).strip()
        blocks.append({"lang": lang, "code": code})
    return blocks


def _extract_shell_commands(text: str) -> list:
    commands = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('$ '):
            commands.append(stripped[2:])
        elif stripped.startswith('> '):
            commands.append(stripped[2:])
        elif re.match(r'^(sudo |apt |npm |pip |mkdir |cd |ls |cat |echo |touch |cp |mv |rm |curl |wget |python |node |git )', stripped):
            if len(stripped) < 200 and not stripped.endswith(':'):
                commands.append(stripped)
    return commands


def _extract_file_writes(text: str, code_blocks: list) -> Optional[dict]:
    for block in code_blocks:
        path_patterns = [
            r'(?:file|simpan|buat|tulis|save).*?[`"\']([/\w._-]+\.\w+)[`"\']',
            r'[`"\']([/\w._-]+\.\w{1,5})[`"\']',
        ]
        search_region = text[:text.find(block["code"])] if block["code"] in text else text
        last_500 = search_region[-500:] if len(search_region) > 500 else search_region

        for pattern in path_patterns:
            match = re.search(pattern, last_500, re.IGNORECASE)
            if match:
                path = match.group(1)
                if not path.startswith('/'):
                    path = f"/tmp/agent_workspace/{path}"
                return {"path": path, "content": block["code"]}

    for block in code_blocks:
        if block["lang"] in ["html", "css", "js", "javascript", "python", "py", "json", "tsx", "jsx", "ts", "php", "java", "c", "cpp", "go", "rust", "rb", "ruby"]:
            ext_map = {
                "html": "index.html", "css": "style.css", "js": "script.js",
                "javascript": "script.js", "python": "main.py", "py": "main.py",
                "json": "data.json", "tsx": "App.tsx", "jsx": "App.jsx",
                "ts": "index.ts", "php": "index.php", "java": "Main.java",
                "go": "main.go", "rust": "main.rs", "rb": "main.rb", "ruby": "main.rb",
                "c": "main.c", "cpp": "main.cpp",
            }
            filename = ext_map.get(block["lang"], f"file.{block['lang']}")
            return {"path": f"/tmp/agent_workspace/{filename}", "content": block["code"]}

    return None


def interpret_response(llm_text: str, user_prompt: str, step: int, history: list) -> ParsedAction:
    code_blocks = _extract_code_blocks(llm_text)
    shell_commands = _extract_shell_commands(llm_text)

    bash_blocks = [b for b in code_blocks if b["lang"] in ["bash", "sh", "shell", "console", "terminal", ""]]
    code_only_blocks = [b for b in code_blocks if b["lang"] not in ["bash", "sh", "shell", "console", "terminal", ""]]

    if bash_blocks:
        cmd = bash_blocks[0]["code"]
        lines = [l for l in cmd.split('\n') if l.strip() and not l.strip().startswith('#')]
        if lines:
            command = " && ".join(lines) if len(lines) <= 5 else lines[0]
            thought_excerpt = llm_text[:200].replace('\n', ' ').strip()
            return ParsedAction(
                thought=thought_excerpt,
                action="terminal",
                action_input={"command": command}
            )

    if code_only_blocks and step <= 2:
        file_write = _extract_file_writes(llm_text, code_only_blocks)
        if file_write:
            thought_excerpt = llm_text[:200].replace('\n', ' ').strip()
            return ParsedAction(
                thought=thought_excerpt,
                action="file_editor",
                action_input={"action": "write", "path": file_write["path"], "content": file_write["content"]}
            )

    if shell_commands:
        thought_excerpt = llm_text[:200].replace('\n', ' ').strip()
        return ParsedAction(
            thought=thought_excerpt,
            action="terminal",
            action_input={"command": shell_commands[0]}
        )

    if code_only_blocks:
        file_write = _extract_file_writes(llm_text, code_only_blocks)
        if file_write:
            thought_excerpt = llm_text[:200].replace('\n', ' ').strip()
            return ParsedAction(
                thought=thought_excerpt,
                action="file_editor",
                action_input={"action": "write", "path": file_write["path"], "content": file_write["content"]}
            )

    search_indicators = ["cari", "search", "temukan", "find", "informasi", "data tentang", "apa itu"]
    if any(ind in user_prompt.lower() for ind in search_indicators) and step == 1:
        return ParsedAction(
            thought=f"Mencari informasi tentang: {user_prompt}",
            action="web_search",
            action_input={"query": user_prompt}
        )

    return ParsedAction(
        thought="Menganalisis respons dan memberikan jawaban",
        action="finish",
        action_input={"answer": llm_text}
    )


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


def call_llm(user_prompt: str, history: str, memories: str = "", step: int = 1, history_list: list = None):
    history_section = ""
    if history and history.strip():
        history_section = f"LANGKAH YANG SUDAH DILAKUKAN:\n{history}\n\nLanjutkan ke langkah berikutnya. Jangan ulangi langkah sebelumnya."
    else:
        history_section = "Ini adalah langkah pertama. Mulai dari awal."

    memory_section = ""
    if memories and memories.strip():
        memory_section = f"INFORMASI TAMBAHAN DARI MEMORI:\n{memories}"

    full_prompt = PLANNER_PROMPT.format(
        user_prompt=user_prompt,
        history_section=history_section,
        memory_section=memory_section,
    )

    try:
        llm_text = _call_api(full_prompt)
        print(f"[LLM] Raw response ({len(llm_text)} chars): {llm_text[:500]}")

        json_parsed = _try_parse_json_format(llm_text)
        if json_parsed:
            print(f"[LLM] Parsed as JSON: action={json_parsed.action}")
            return json_parsed, llm_text

        parsed = interpret_response(llm_text, user_prompt, step, history_list or [])
        print(f"[LLM] Interpreted as: action={parsed.action}")
        return parsed, llm_text

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
    history_list = []
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
                call_llm, user_prompt, history_str, memories, i + 1, history_list
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
                "content": parsed.thought[:500]
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
                    save_task_result, user_prompt, answer[:500], "finish"
                )
                task["status"] = "completed"
                break

            await websocket.send_json({
                "type": "tool_start",
                "step": i + 1,
                "tool_name": parsed.action,
                "args": json.dumps(parsed.action_input, ensure_ascii=False)[:500]
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

            history_entry = {
                "step": i + 1,
                "thought": parsed.thought[:200],
                "action": parsed.action,
                "input": parsed.action_input,
                "output": tool_output[:500],
                "error": has_error,
            }
            history_list.append(history_entry)

            history_lines.append(f"Step {i+1}:")
            history_lines.append(f"  Thought: {parsed.thought[:200]}")
            history_lines.append(f"  Action: {parsed.action}")
            history_lines.append(f"  Action Input: {json.dumps(parsed.action_input, ensure_ascii=False)[:300]}")
            history_lines.append(f"  Result: {tool_output[:500]}")
            if has_error:
                history_lines.append(f"  STATUS: ERROR - perlu diperbaiki di langkah berikutnya")
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
