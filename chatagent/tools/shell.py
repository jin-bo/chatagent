"""Shell command execution tool."""

import subprocess
from typing import Any, Dict

from .base import Tool


class ShellTool(Tool):
    """Tool for executing shell commands."""

    @property
    def name(self) -> str:
        return "run_shell_command"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution as it can execute any command."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory for the command (defaults to current directory)",
                    "default": ".",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        }

    def execute(
        self, command: str, working_directory: str = ".", timeout: float = 30
    ) -> str:
        """Execute shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = []
            if result.stdout:
                output.append(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                output.append(f"STDERR:\n{result.stderr}")
            output.append(f"\nReturn code: {result.returncode}")

            return "\n\n".join(output) if output else "Command completed with no output"

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds"
        except Exception as e:
            return f"Error executing command: {str(e)}"
