"""Search tools."""

from pathlib import Path
from typing import Any, Dict
import fnmatch
import re

from .base import Tool


class FindFilesTool(Tool):
    """Tool for finding files using glob patterns."""

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return "Find files matching a glob pattern (e.g., '*.py', '**/*.txt'). Supports recursive search with '**'."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '*.py', 'src/**/*.js')",
                },
                "directory": {
                    "type": "string",
                    "description": "Base directory to search from (defaults to current directory)",
                    "default": ".",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, pattern: str, directory: str = ".") -> str:
        """Find files matching pattern."""
        try:
            path = Path(directory).expanduser()
            if not path.exists():
                return f"Error: Directory {directory} does not exist"

            matches = []
            if "**" in pattern:
                # Recursive search
                for item in path.rglob(pattern.replace("**/", "")):
                    if item.is_file():
                        matches.append(str(item.relative_to(path)))
            else:
                # Non-recursive search
                for item in path.glob(pattern):
                    if item.is_file():
                        matches.append(str(item.relative_to(path)))

            if not matches:
                return f"No files found matching pattern: {pattern}"

            return f"Found {len(matches)} file(s):\n\n" + "\n".join(sorted(matches))
        except Exception as e:
            return f"Error finding files: {str(e)}"


class SearchTextTool(Tool):
    """Tool for searching text content in files."""

    @property
    def name(self) -> str:
        return "search_file_content"

    @property
    def description(self) -> str:
        return "Search for text patterns in files. Supports regex patterns and can search across multiple files."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File glob pattern to search in (e.g., '*.py', '**/*.txt')",
                    "default": "**/*",
                },
                "directory": {
                    "type": "string",
                    "description": "Base directory to search from",
                    "default": ".",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether to perform case-sensitive search",
                    "default": True,
                },
                "regex": {
                    "type": "boolean",
                    "description": "Whether to treat pattern as regex",
                    "default": False,
                },
            },
            "required": ["pattern"],
        }

    def execute(
        self,
        pattern: str,
        file_pattern: str = "**/*",
        directory: str = ".",
        case_sensitive: bool = True,
        regex: bool = False,
    ) -> str:
        """Search for text in files."""
        try:
            path = Path(directory).expanduser()
            if not path.exists():
                return f"Error: Directory {directory} does not exist"

            # Compile regex pattern
            if regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                try:
                    compiled_pattern = re.compile(pattern, flags)
                except re.error as e:
                    return f"Error: Invalid regex pattern: {str(e)}"
            else:
                if not case_sensitive:
                    pattern = pattern.lower()

            # Find files to search
            files_to_search = []
            if "**" in file_pattern:
                files_to_search = list(path.rglob(file_pattern.replace("**/", "")))
            else:
                files_to_search = list(path.glob(file_pattern))

            results = []
            for file_path in files_to_search:
                if not file_path.is_file():
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            match = False
                            if regex:
                                match = compiled_pattern.search(line) is not None
                            else:
                                search_line = line if case_sensitive else line.lower()
                                match = pattern in search_line

                            if match:
                                rel_path = file_path.relative_to(path)
                                results.append(f"{rel_path}:{line_num}: {line.rstrip()}")
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary files or files we can't read
                    continue

            if not results:
                return f"No matches found for pattern: {pattern}"

            result_text = f"Found {len(results)} match(es):\n\n"
            # Limit results to avoid overwhelming output
            if len(results) > 100:
                result_text += "\n".join(results[:100])
                result_text += f"\n\n... and {len(results) - 100} more matches"
            else:
                result_text += "\n".join(results)

            return result_text
        except Exception as e:
            return f"Error searching files: {str(e)}"
