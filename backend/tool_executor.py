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


def execute_tool(action: str, action_input: dict) -> str:
    if action not in AVAILABLE_TOOLS:
        return f"Error: Tool '{action}' not found. Available tools: {', '.join(AVAILABLE_TOOLS.keys())}"

    tool_function = AVAILABLE_TOOLS[action]

    try:
        result = tool_function(**action_input)
        return result
    except TypeError as e:
        return f"Error: Invalid arguments for tool '{action}': {e}"
    except Exception as e:
        return f"Error executing tool '{action}': {e}"
