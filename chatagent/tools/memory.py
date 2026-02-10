"""Memory tool for saving important information."""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

from .base import Tool


class SaveMemoryTool(Tool):
    """Tool for saving important information to memory."""

    def __init__(self, memory_file: str = ".chatagent_memory.json"):
        """Initialize memory tool.

        Args:
            memory_file: Path to the memory file
        """
        self.memory_file = Path(memory_file).expanduser()
        self._ensure_memory_file()

    def _ensure_memory_file(self):
        """Ensure memory file exists."""
        if not self.memory_file.exists():
            self.memory_file.write_text(json.dumps({"memories": []}, indent=2))

    @property
    def name(self) -> str:
        return "save_memory"

    @property
    def description(self) -> str:
        return "Save important information to memory for future reference. Use this to remember user preferences, project context, or important facts."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "A short identifier for this memory (e.g., 'user_preference', 'project_context')",
                },
                "value": {
                    "type": "string",
                    "description": "The information to remember",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for categorizing this memory",
                },
            },
            "required": ["key", "value"],
        }

    def execute(self, key: str, value: str, tags: list = None) -> str:
        """Save information to memory."""
        try:
            # Load existing memories
            with open(self.memory_file, "r") as f:
                data = json.load(f)

            memories = data.get("memories", [])

            # Create new memory entry
            memory = {
                "key": key,
                "value": value,
                "timestamp": datetime.now().isoformat(),
                "tags": tags or [],
            }

            # Update or append
            updated = False
            for i, m in enumerate(memories):
                if m.get("key") == key:
                    memories[i] = memory
                    updated = True
                    break

            if not updated:
                memories.append(memory)

            # Save back to file
            data["memories"] = memories
            with open(self.memory_file, "w") as f:
                json.dump(data, f, indent=2)

            action = "Updated" if updated else "Saved"
            return f"{action} memory: {key}"

        except Exception as e:
            return f"Error saving memory: {str(e)}"

    def get_all_memories(self) -> list:
        """Get all saved memories.

        Returns:
            List of memory entries
        """
        try:
            with open(self.memory_file, "r") as f:
                data = json.load(f)
            return data.get("memories", [])
        except Exception:
            return []

    def search_memories(self, query: str) -> list:
        """Search memories by key or tags.

        Args:
            query: Search query

        Returns:
            List of matching memories
        """
        memories = self.get_all_memories()
        query_lower = query.lower()

        results = []
        for memory in memories:
            if query_lower in memory.get("key", "").lower():
                results.append(memory)
            elif any(query_lower in tag.lower() for tag in memory.get("tags", [])):
                results.append(memory)

        return results
