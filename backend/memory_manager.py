import json
import os
import time
from typing import List, Dict

MEMORY_FILE = "/tmp/agent_memory.json"
MAX_MEMORIES = 100


def _load_memories() -> List[Dict]:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_memories(memories: List[Dict]):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[MEMORY] Failed to save: {e}")


def save_memory(text: str, category: str = "general", metadata: dict = None):
    if not text or not text.strip():
        return

    memories = _load_memories()

    entry = {
        "text": text.strip()[:1000],
        "category": category,
        "timestamp": time.time(),
        "metadata": metadata or {},
    }

    memories.append(entry)

    if len(memories) > MAX_MEMORIES:
        memories = memories[-MAX_MEMORIES:]

    _save_memories(memories)
    print(f"[MEMORY] Saved memory ({category}): {text[:80]}...")


def retrieve_memories(query: str, limit: int = 5) -> str:
    memories = _load_memories()

    if not memories:
        return ""

    query_words = set(query.lower().split())
    scored = []

    for mem in memories:
        mem_words = set(mem["text"].lower().split())
        overlap = len(query_words & mem_words)
        recency_bonus = min(mem.get("timestamp", 0) / 1e10, 0.5)
        score = overlap + recency_bonus
        if score > 0:
            scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        recent = memories[-limit:]
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


def save_task_result(task: str, result: str, tool_used: str = ""):
    save_memory(
        f"Task: {task[:200]} | Tool: {tool_used} | Result: {result[:300]}",
        category="task_result",
        metadata={"tool": tool_used},
    )


def save_search_result(query: str, result: str):
    save_memory(
        f"Search '{query[:100]}': {result[:500]}",
        category="search",
        metadata={"query": query},
    )


def clear_memories():
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
    print("[MEMORY] All memories cleared.")
