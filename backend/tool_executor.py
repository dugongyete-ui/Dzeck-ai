import subprocess
import json
import os
import urllib.parse
import requests

AGENT_WORKSPACE = "/tmp/agent_workspace"

os.makedirs(AGENT_WORKSPACE, exist_ok=True)


def _call_llm_for_search(query: str) -> str:
    encoded_q = urllib.parse.quote(f"Search the web for: {query}")
    url = f"https://magma-api.biz.id/ai/copilot?prompt={encoded_q}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    try:
        data = resp.json()
    except Exception:
        return resp.text

    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, dict):
            return result.get("response", result.get("text", json.dumps(result)))
        if isinstance(result, str):
            return result
        r = data.get("response")
        if isinstance(r, str):
            return r
        return json.dumps(data)
    return str(data)


def web_search(query: str) -> str:
    print(f"--- TOOL: web_search for '{query}' ---")
    try:
        result = _call_llm_for_search(query)
        return result if result.strip() else "No results found."
    except Exception as e:
        return f"Web search error: {e}"


def terminal(command: str) -> str:
    print(f"--- TOOL: terminal '{command}' ---")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=AGENT_WORKSPACE,
        )
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}"
        if result.stderr:
            if output:
                output += "\n"
            output += f"STDERR:\n{result.stderr}"
        if not output.strip():
            output = "(command executed successfully, no output)"
        if result.returncode != 0:
            output += f"\n(exit code: {result.returncode})"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Terminal error: {e}"


def file_editor(action: str, path: str, content: str = "") -> str:
    print(f"--- TOOL: file_editor action='{action}' path='{path}' ---")

    if not path.startswith(AGENT_WORKSPACE):
        path = os.path.join(AGENT_WORKSPACE, path.lstrip("/"))

    try:
        if action == "read":
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = f.read()
                return data if data else "(file is empty)"
            return f"File not found: {path}"

        elif action == "write":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"File written successfully: {path}"

        elif action == "append":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                f.write(content)
            return f"Content appended to: {path}"

        else:
            return f"Unknown file action: {action}. Use 'read', 'write', or 'append'."
    except Exception as e:
        return f"File editor error: {e}"


def finish(answer: str) -> str:
    print(f"--- TOOL: finish ---")
    return answer


AVAILABLE_TOOLS = {
    "web_search": web_search,
    "terminal": terminal,
    "file_editor": file_editor,
    "finish": finish,
}

TOOL_ARG_MAP = {
    "web_search": {"q": "query", "search": "query", "keyword": "query", "keywords": "query", "search_query": "query"},
    "terminal": {"cmd": "command", "shell": "command", "exec": "command", "run": "command"},
    "file_editor": {"file_path": "path", "filepath": "path", "filename": "path", "file": "path", "text": "content", "data": "content", "body": "content", "operation": "action", "mode": "action", "type": "action"},
    "finish": {"result": "answer", "response": "answer", "message": "answer", "output": "answer", "summary": "answer"},
}


def _normalize_args(action: str, action_input: dict) -> dict:
    if "raw" in action_input and len(action_input) == 1:
        raw_val = action_input["raw"]
        if action == "web_search":
            return {"query": raw_val}
        elif action == "terminal":
            return {"command": raw_val}
        elif action == "finish":
            return {"answer": raw_val}

    if action not in TOOL_ARG_MAP:
        return action_input

    alias_map = TOOL_ARG_MAP[action]
    normalized = {}
    for key, value in action_input.items():
        canonical = alias_map.get(key.lower(), key)
        normalized[canonical] = value

    return normalized


def execute_tool(action: str, action_input: dict) -> str:
    action = action.strip().lower()

    if action not in AVAILABLE_TOOLS:
        return f"Error: Tool '{action}' not found. Available tools: {', '.join(AVAILABLE_TOOLS.keys())}"

    normalized_input = _normalize_args(action, action_input)
    tool_function = AVAILABLE_TOOLS[action]

    try:
        result = tool_function(**normalized_input)
        return result if result else "(no output)"
    except TypeError as e:
        print(f"[TOOL] TypeError for '{action}' with args {normalized_input}: {e}")
        try:
            if action == "web_search":
                first_val = next(iter(normalized_input.values()), "")
                return web_search(query=str(first_val))
            elif action == "terminal":
                first_val = next(iter(normalized_input.values()), "")
                return terminal(command=str(first_val))
            elif action == "file_editor":
                return f"File editor requires 'action' and 'path' arguments. Got: {list(normalized_input.keys())}"
            elif action == "finish":
                first_val = next(iter(normalized_input.values()), "Task completed.")
                return finish(answer=str(first_val))
        except Exception as fallback_e:
            return f"Error executing tool '{action}': {fallback_e}"
        return f"Error: Invalid arguments for tool '{action}': {e}. Expected args: {list(normalized_input.keys())}"
    except Exception as e:
        return f"Error executing tool '{action}': {e}"
