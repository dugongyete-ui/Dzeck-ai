import json
import os
import time
import threading
from typing import List, Dict

BASE_MEMORY_DIR = "/tmp/agent_memories"
MAX_MEMORIES = 100

os.makedirs(BASE_MEMORY_DIR, exist_ok=True)

_memory_lock = threading.Lock()


def _get_memory_file(session_id: str = "global") -> str:
    return os.path.join(BASE_MEMORY_DIR, f"{session_id}.json")


def _load_memories(session_id: str = "global") -> List[Dict]:
    memory_file = _get_memory_file(session_id)
    if os.path.exists(memory_file):
        try:
            with open(memory_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_memories(memories: List[Dict], session_id: str = "global"):
    memory_file = _get_memory_file(session_id)
    try:
        with _memory_lock:
            with open(memory_file, "w") as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[MEMORY] Failed to save: {e}")


def save_memory(text: str, category: str = "general", metadata: dict = None, session_id: str = "global"):
    if not text or not text.strip():
        return

    with _memory_lock:
        memories = _load_memories(session_id)

    entry = {
        "text": text.strip()[:1000],
        "category": category,
        "timestamp": time.time(),
        "metadata": metadata or {},
    }

    memories.append(entry)

    if len(memories) > MAX_MEMORIES:
        memories = memories[-MAX_MEMORIES:]

    _save_memories(memories, session_id)
    print(f"[MEMORY:{session_id[:8]}] Saved ({category}): {text[:60]}...")


def retrieve_memories(query: str, limit: int = 5, session_id: str = "global") -> str:
    with _memory_lock:
        session_memories = _load_memories(session_id)
        global_memories = _load_memories("global") if session_id != "global" else []

    all_memories = session_memories + global_memories

    if not all_memories:
        return ""

    query_words = set(query.lower().split())
    scored = []

    for mem in all_memories:
        mem_words = set(mem["text"].lower().split())
        overlap = len(query_words & mem_words)
        recency_bonus = min(mem.get("timestamp", 0) / 1e10, 0.5)
        score = overlap + recency_bonus
        if score > 0:
            scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        recent = all_memories[-limit:]
        if recent:
            lines = []
            for mem in recent:
                lines.append(f"- [{mem['category']}] {mem['text']}")
            return "\n".join(lines)
        return ""

    lines = []
    for _, mem in scored[:limit]:
        lines.append(f"- [{mem['category']}] {mem['text']}")

    return "\n".join(lines)


def save_task_result(task: str, result: str, tool_used: str = "", session_id: str = "global"):
    save_memory(
        f"Task: {task[:200]} | Tool: {tool_used} | Result: {result[:300]}",
        category="task_result",
        metadata={"tool": tool_used},
        session_id=session_id,
    )


def save_search_result(query: str, result: str, session_id: str = "global"):
    save_memory(
        f"Search '{query[:100]}': {result[:500]}",
        category="search",
        metadata={"query": query},
        session_id=session_id,
    )


def clear_memories(session_id: str = "global"):
    memory_file = _get_memory_file(session_id)
    if os.path.exists(memory_file):
        os.remove(memory_file)
    print(f"[MEMORY:{session_id[:8]}] Cleared.")


def cleanup_old_memories(max_age_hours: int = 24):
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    cleaned = 0
    try:
        for filename in os.listdir(BASE_MEMORY_DIR):
            filepath = os.path.join(BASE_MEMORY_DIR, filename)
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                if file_age > max_age_seconds and filename != "global.json":
                    os.remove(filepath)
                    cleaned += 1
        if cleaned:
            print(f"[MEMORY] Cleaned up {cleaned} old memory files.")
    except Exception as e:
        print(f"[MEMORY] Cleanup error: {e}")
