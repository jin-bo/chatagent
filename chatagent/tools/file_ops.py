"""File operation tools."""

import os
from pathlib import Path
from typing import Any, Dict

from .base import Tool


class ReadFileTool(Tool):
    """Tool for reading file contents."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Returns the file content as text."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read (can be absolute or relative)",
                }
            },
            "required": ["file_path"],
        }

    def execute(self, file_path: str) -> str:
        """Read file contents."""
        try:
            path = Path(file_path).expanduser()
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return f"File: {file_path}\n\n{content}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool for writing content to a file."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        }

    @property
    def requires_confirmation(self) -> bool:
        """File writing requires user confirmation to prevent data loss."""
        return True

    def execute(self, file_path: str, content: str) -> str:
        """Write content to file."""
        try:
            path = Path(file_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditTool(Tool):
    """Tool for editing files by replacing text."""

    @property
    def name(self) -> str:
        return "replace"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old text with new text. The old text must match exactly."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to replace",
                },
                "new_text": {
                    "type": "string",
                    "description": "The new text to insert",
                },
            },
            "required": ["file_path", "old_text", "new_text"],
        }

    def execute(self, file_path: str, old_text: str, new_text: str) -> str:
        """Replace text in file."""
        try:
            path = Path(file_path).expanduser()
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if old_text not in content:
                return f"Error: Old text not found in {file_path}"

            new_content = content.replace(old_text, new_text, 1)

            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully edited {file_path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"


class ReadFolderTool(Tool):
    """Tool for listing directory contents."""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List the contents of a directory, showing files and subdirectories."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Path to the directory to list (defaults to current directory)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list recursively",
                    "default": False,
                },
            },
            "required": [],
        }

    def execute(self, directory_path: str = ".", recursive: bool = False) -> str:
        """List directory contents."""
        try:
            path = Path(directory_path).expanduser()
            if not path.exists():
                return f"Error: Directory {directory_path} does not exist"

            if not path.is_dir():
                return f"Error: {directory_path} is not a directory"

            results = []
            if recursive:
                for item in path.rglob("*"):
                    rel_path = item.relative_to(path)
                    if item.is_dir():
                        results.append(f"[DIR]  {rel_path}/")
                    else:
                        size = item.stat().st_size
                        results.append(f"[FILE] {rel_path} ({size} bytes)")
            else:
                for item in sorted(path.iterdir()):
                    if item.is_dir():
                        results.append(f"[DIR]  {item.name}/")
                    else:
                        size = item.stat().st_size
                        results.append(f"[FILE] {item.name} ({size} bytes)")

            return f"Directory: {directory_path}\n\n" + "\n".join(results)
        except Exception as e:
            return f"Error listing directory: {str(e)}"
