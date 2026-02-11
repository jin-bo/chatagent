"""CLI interface for ChatAgent."""

import os
import sys
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.theme import Theme
from dotenv import load_dotenv

from .agent import ChatAgent

# Custom theme for the CLI
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
})

console = Console(theme=custom_theme)


class ChatAgentCLI:
    """CLI interface for ChatAgent."""

    def __init__(self):
        """Initialize CLI."""
        load_dotenv()

        self.agent = ChatAgent(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            model=os.getenv("OPENAI_MODEL"),
            confirmation_callback=self.confirm_tool_execution,
        )

    def confirm_tool_execution(self, tool_name: str, tool_description: str, tool_args: dict) -> bool:
        """Prompt user to confirm tool execution.

        Args:
            tool_name: Name of the tool to execute
            tool_description: Description of the tool
            tool_args: Arguments to pass to the tool

        Returns:
            True if user confirms, False otherwise
        """
        console.print(f"\n[yellow]⚠️  Tool Confirmation Required[/yellow]")
        console.print(f"[info]Tool:[/info] [cyan]{tool_name}[/cyan]")
        console.print(f"[info]Description:[/info] {tool_description}")
        console.print(f"[info]Arguments:[/info]")

        # Format arguments nicely
        for key, value in tool_args.items():
            # Truncate long values
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            console.print(f"  • {key}: {value_str}")

        # Ask for confirmation
        confirmed = Confirm.ask("\n[bold]Do you want to execute this tool?[/bold]", default=False)

        return confirmed

    def print_welcome(self):
        """Print welcome message."""
        current_model = self.agent.get_current_model()
        welcome = f"""
# ChatAgent

A CLI chat agent with tools and skills support.

**Current Model:** `{current_model}`

**Commands:**
- `/help` - Show help message
- `/model` - List or switch models
- `/clear` - Clear conversation history
- `/status` - Show conversation status
- `/skills` - List available skills
- `/memory` - Show saved memories
- `/exit` or `/quit` - Exit the program

**Features:**
- Multi-turn conversations with context
- File operations (read, write, edit)
- Code search and analysis
- Web fetching and search
- Memory system
- Claude Skills support

Type your message to start chatting, or `/help` for more information!
"""
        console.print(Panel(Markdown(welcome), title="Welcome", border_style="cyan"))

    def print_help(self):
        """Print help message."""
        help_text = """
# ChatAgent Help

**Available Commands:**
All commands start with `/`:

- `/help` - Show this help message
- `/model` - List available models or switch model
  - `/model` - Show current model and available models
  - `/model <name>` - Switch to specified model
- `/clear` - Clear conversation history
- `/status` - Show conversation status
- `/skills` - List available skills
- `/memory` - Show saved memories
- `/exit` or `/quit` - Exit the program

**Available Tools:**
The agent has access to the following tools:
- `read_file` - Read file contents
- `write_file` - Write content to files
- `replace` - Edit files by replacing text
- `list_directory` - List directory contents
- `glob` - Find files matching patterns
- `search_file_content` - Search text in files
- `run_shell_command` - Execute shell commands
- `web_fetch` - Fetch web content
- `google_web_search` - Search the web
- `save_memory` - Save important information
- `activate_skill` - Activate Claude skills
- `cli_help` - Get CLI help
- `codebase_investigator` - Investigate codebases

**Skills:**
Type `/skills` to see available skills, or ask the agent to activate a specific skill.

**Examples:**
- "Read the file main.py"
- "Search for function definitions in Python files"
- "Fetch content from https://example.com"
- "Activate the pdf skill to help me work with PDF files"

**Note:** Regular messages (without `/`) are sent to the AI agent.
"""
        console.print(Markdown(help_text))

    def list_skills(self):
        """List available skills."""
        skills = self.agent.skill_manager.list_available_skills()

        console.print(f"\n[info]Available Skills ({len(skills)} loaded):[/info]\n")
        for skill_name in sorted(skills):
            skill_info = self.agent.skill_manager.get_skill_info(skill_name)
            title = skill_info.get('title', skill_name) if skill_info else skill_name
            desc = skill_info.get('description', 'No description')[:100] if skill_info else 'No description'
            console.print(f"  • [cyan]{skill_name}[/cyan] - {title}")
            if desc:
                console.print(f"    {desc}...")

        console.print("\n[info]Active Skills:[/info]")
        active = self.agent.skill_manager.get_active_skills()
        if active:
            for skill, info in active.items():
                console.print(f"  • [success]{skill}[/success]: {info['task']}")
        else:
            console.print("  None")
        console.print()

    def show_status(self):
        """Show conversation status."""
        summary = self.agent.get_conversation_summary()
        console.print(f"\n[info]Status:[/info] {summary}\n")

    def show_memories(self):
        """Show saved memories."""
        memories = self.agent.memory_tool.get_all_memories()

        if not memories:
            console.print("\n[warning]No memories saved yet.[/warning]\n")
            return

        console.print("\n[info]Saved Memories:[/info]\n")
        for memory in memories:
            console.print(f"  • [cyan]{memory['key']}[/cyan]: {memory['value']}")
            if memory.get('tags'):
                console.print(f"    Tags: {', '.join(memory['tags'])}")
            console.print(f"    Saved: {memory['timestamp']}")
            console.print()

    def handle_model_command(self, args: str):
        """Handle model command.

        Args:
            args: Command arguments (model name or empty for list)
        """
        args = args.strip()

        if not args:
            # Show current model and available models
            current = self.agent.get_current_model()
            available = self.agent.list_available_models()

            console.print(f"\n[info]Current Model:[/info] [cyan]{current}[/cyan]\n")
            console.print("[info]Available Models:[/info]\n")

            # Group by provider
            claude_models = [m for m in available if m.startswith("claude-")]
            gpt_models = [m for m in available if m.startswith("gpt-")]
            other_models = [m for m in available if not m.startswith(("claude-", "gpt-"))]

            if claude_models:
                console.print("  [bold]Claude:[/bold]")
                for model in claude_models:
                    marker = " [green]✓[/green]" if model == current else ""
                    console.print(f"    • {model}{marker}")

            if gpt_models:
                console.print("\n  [bold]OpenAI GPT:[/bold]")
                for model in gpt_models:
                    marker = " [green]✓[/green]" if model == current else ""
                    console.print(f"    • {model}{marker}")

            if other_models:
                console.print("\n  [bold]Other:[/bold]")
                for model in other_models:
                    marker = " [green]✓[/green]" if model == current else ""
                    console.print(f"    • {model}{marker}")

            console.print("\n[info]Usage:[/info] /model <model_name>")
            console.print("Example: /model claude-sonnet-4-5\n")

        else:
            # Switch to specified model
            result = self.agent.set_model(args)
            console.print(f"\n[success]{result}[/success]\n")

    def run(self):
        """Run the CLI."""
        self.print_welcome()

        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

                if not user_input.strip():
                    continue

                # Handle commands (all start with /)
                input_text = user_input.strip()

                # Check if it's a command
                if input_text.startswith('/'):
                    # Split command and arguments
                    parts = input_text[1:].split(maxsplit=1)
                    command = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""

                    if command in ["exit", "quit"]:
                        console.print("\n[success]Goodbye![/success]\n")
                        break

                    elif command == "help":
                        self.print_help()
                        continue

                    elif command == "clear":
                        self.agent.clear_history()
                        console.print("\n[success]Conversation history cleared.[/success]\n")
                        continue

                    elif command == "status":
                        self.show_status()
                        continue

                    elif command == "skills":
                        self.list_skills()
                        continue

                    elif command == "memory":
                        self.show_memories()
                        continue

                    elif command == "model":
                        self.handle_model_command(args)
                        continue

                    else:
                        console.print(f"\n[error]Unknown command: /{command}[/error]")
                        console.print("Type [cyan]/help[/cyan] for available commands.\n")
                        continue

                # Process with agent
                console.print("\n[bold green]Assistant[/bold green]")
                with console.status("[bold yellow]Thinking...", spinner="dots"):
                    response = self.agent.chat(user_input)

                # Display response
                console.print(Markdown(response))

            except KeyboardInterrupt:
                console.print("\n\n[warning]Interrupted. Type '/exit' to quit.[/warning]")
                continue

            except Exception as e:
                console.print(f"\n[error]Error: {str(e)}[/error]\n")
                continue


def main():
    """Main entry point."""
    try:
        cli = ChatAgentCLI()
        cli.run()
    except KeyboardInterrupt:
        console.print("\n\n[success]Goodbye![/success]\n")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[error]Fatal error: {str(e)}[/error]\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
