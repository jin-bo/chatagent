# ChatAgent

A powerful CLI chat agent with tools and Claude Skills support. Built with Python and designed to work with any OpenAI-compatible API.

## Features

### 🤖 Intelligent Agent
- Multi-turn conversations with context
- Function calling for tool usage
- Smart tool selection and execution
- Memory system for saving important information
- **Complete logging** of all LLM interactions to `chatagent.log`
- **Auto-loading of project instructions** from `CHATAGENT.md` at startup
- **🔒 Tool confirmation** - User confirmation required for Shell & Web tools
- **📅 Current date context** - System prompt includes current date and time

### 🛠️ Comprehensive Tools

**File Operations:**
- `read_file` - Read file contents
- `write_file` - Write content to files
- `replace` - Edit files by replacing text
- `list_directory` - List directory contents

**Search & Discovery:**
- `glob` - Find files matching patterns (supports `**` for recursive search)
- `search_file_content` - Search text in files with regex support
- `codebase_investigator` - Analyze project structure

**Shell & Web:**
- `run_shell_command` - Execute shell commands
- `web_fetch` - Fetch and extract content from URLs
- `google_web_search` - Search the web (uses DuckDuckGo)

**Special Features:**
- `save_memory` - Save important information for future reference
- `activate_skill` - Activate Claude skills for specialized tasks
- `cli_help` - Get help with CLI usage

### 🎯 Dynamic Skills System

**17 skills automatically loaded** from the `skills/` directory:
- **pdf** - PDF processing and manipulation
- **xlsx** - Excel and spreadsheet operations
- **pptx** - PowerPoint presentations
- **docx** - Word document handling
- **doc-coauthoring** - Structured documentation workflow
- **frontend-design** - Create web interfaces
- **algorithmic-art** - Generate algorithmic art
- **mcp-builder** - Build MCP servers
- **webapp-testing** - Test web applications
- **theme-factory** - Style artifacts with themes
- **canvas-design** - Create visual art
- **brand-guidelines** - Anthropic brand styling
- **slack-gif-creator** - Create Slack GIFs
- **internal-comms** - Internal communications
- **web-artifacts-builder** - Build HTML artifacts
- **skill-creator** - Create new skills
- **research-wbs-review** - Review WBS structures

Skills are loaded dynamically from `SKILL.md` files in subdirectories. Add new skills by creating a directory with a `SKILL.md` file!

## Installation

### Prerequisites
- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- An OpenAI API key or access to an OpenAI-compatible API

### Quick Start with uv (Recommended)

uv is a fast Python package manager. If you don't have it, install it first:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then set up ChatAgent:

1. Navigate to the project directory:
```bash
cd chatagent
```

2. Sync dependencies (uv will create a virtual environment automatically):
```bash
uv sync
```

3. Configure your API credentials:
```bash
cp .env.example .env
# Edit .env and add your API key
```

### Alternative: Setup with pip

If you prefer using pip:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Configure API
cp .env.example .env
# Edit .env and add your API key
```

## Project Instructions

ChatAgent automatically loads project-specific instructions from `CHATAGENT.md` if it exists in the current directory. This file is injected into the system prompt at the start of each session, allowing you to define:

- Code style and conventions
- Project structure and patterns
- Development workflows
- Testing approaches
- Common commands and best practices

The `CHATAGENT.md` file is automatically detected and loaded when the agent starts. If the file doesn't exist, the agent continues to work normally with its default instructions.

See the included `CHATAGENT.md` for an example of project-specific instructions for this codebase.

## Tool Confirmation (Safety Feature)

For security, ChatAgent requires user confirmation before executing potentially dangerous tools:

**Tools requiring confirmation:**
- 🔧 **`run_shell_command`** - Shell command execution
- 🌐 **`web_fetch`** - Fetching web content
- 🌐 **`google_web_search`** - Web search

**How it works:**
1. When the agent wants to use these tools, execution pauses
2. You see a menu with tool details and confirmation options
3. Press a single key to choose (no Enter needed):
   - **1** - Yes, execute this tool once
   - **2** - Yes to all, execute and allow all tools for this session
   - **3** - No, cancel execution
   - **Esc** - Cancel execution
4. If denied, the agent is notified and can try alternative approaches

**Example:**
```
⚠️  Tool Confirmation Required
Tool: run_shell_command
Description: Execute a shell command and return its output
Arguments:
  • command: ls -la
  • working_directory: .

Choose an option:
 1. Yes
 2. Yes, allow all tools during this session
 3. No

Press 1, 2, or 3 (single key, no Enter needed) · Esc to cancel
```

**Single-key input** - Just press the number, no need to press Enter!

**Additional features:**
- Use `/status` to check if "allow all" mode is enabled
- Use `/reset-confirm` to reset to prompt mode (keeps conversation history)
- Use `/clear` to clear conversation AND reset confirmation mode (fresh start)

This prevents accidental or malicious:
- Destructive shell commands
- Unintended web requests
- Exposure of sensitive information

## Current Date Context

ChatAgent automatically includes the current date and time in the system prompt, helping the AI understand temporal context for:

- **Date-aware tasks**: Creating files with timestamps, scheduling, deadlines
- **Time-sensitive queries**: "What happened today?", "Recent changes"
- **Log analysis**: Understanding when events occurred
- **File organization**: Sorting by date, finding recent files

**Format**: `Current Date and Time: 2026-02-11 14:40:58 (Wednesday)`

This information is updated with each new conversation, ensuring the AI always has accurate temporal context.

## Configuration

Edit the `.env` file with your settings:

```env
# Required: Your API key
OPENAI_API_KEY=your-api-key-here

# Optional: Base URL for OpenAI-compatible APIs
# OPENAI_BASE_URL=https://api.openai.com/v1

# Optional: Model name
# OPENAI_MODEL=gpt-4-turbo-preview
```

### Using with Different Providers

**OpenAI:**
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

**Azure OpenAI:**
```env
OPENAI_API_KEY=your-azure-key
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment
OPENAI_MODEL=gpt-4
```

**Other OpenAI-compatible APIs:**
```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.your-provider.com/v1
OPENAI_MODEL=your-model-name
```

## Usage

### Starting the Agent

**With uv (recommended):**
```bash
# Quick start - run directly
uv run python main.py

# Or use the convenience script
./run.sh

# Or use the installed command
uv run chatagent
```

**With pip:**
```bash
# Activate virtual environment first
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Then run
chatagent
# or
python main.py
```

### Commands

All commands start with `/`:

- `/help` - Show help message
- `/model` - List available models or switch model
  - `/model` - Show current model and list available models
  - `/model <name>` - Switch to specified model (e.g., `/model gpt-4`)
  - See [MODEL_SWITCHING.md](MODEL_SWITCHING.md) for detailed guide
- `/clear` - Clear conversation history
- `/status` - Show conversation status (includes current model)
- `/skills` - List available skills
- `/memory` - Show saved memories
- `/exit` or `/quit` - Exit the program

**Note**: Regular messages (without `/`) are sent to the AI agent. All interactions are automatically logged to `chatagent.log` for debugging and analysis.

### Switching Models

ChatAgent supports switching between different LLM models mid-conversation:

```bash
You: /model                    # Show available models
You: /model gpt-4              # Switch to GPT-4
You: /model claude-sonnet-4-5  # Switch to Claude Sonnet
```

Supported models include:
- **Claude**: opus-4, sonnet-4-5, sonnet-4, haiku-4
- **OpenAI**: gpt-4-turbo, gpt-4, gpt-3.5-turbo
- **DeepSeek**: deepseek-chat, deepseek-coder

See [MODEL_SWITCHING.md](MODEL_SWITCHING.md) for complete documentation.

### Example Interactions

**Reading and analyzing files:**
```
You: Read the file main.py and explain what it does

You: Search for all Python files in this directory

You: Find all TODO comments in the codebase
```

**Working with code:**
```
You: Create a new Python file called utils.py with helper functions

You: Replace the old function in utils.py with an improved version

You: Run the tests using pytest
```

**Web and search:**
```
You: Fetch the content from https://example.com

You: Search for Python best practices

You: Find information about async/await in Python
```

**Using commands:**
```
You: /model           (show current model and available models)

You: /model gpt-4     (switch to GPT-4)

You: /skills          (list all available skills)

You: /memory          (show saved memories)

You: /status          (show conversation status and current model)

You: /help            (show help message)
```

**Using skills:**
```
You: Activate the pdf skill to help me merge PDF files

You: Use the xlsx skill to analyze this spreadsheet

You: I need to create a presentation with the pptx skill
```

## Skills System

### Overview

ChatAgent features a **dynamic skills system** that loads skill definitions from the `skills/` directory. Each skill is defined in its own subdirectory with a `SKILL.md` file containing documentation and metadata.

### Available Skills (17 Total)

Skills are automatically discovered and loaded at startup. Current skills include:

| Skill | Description |
|-------|-------------|
| **pdf** | PDF processing (merge, split, extract, OCR) |
| **xlsx** | Excel/CSV spreadsheet operations |
| **pptx** | PowerPoint presentation creation and editing |
| **docx** | Word document handling |
| **doc-coauthoring** | Structured documentation workflow |
| **frontend-design** | Production-grade web interfaces |
| **algorithmic-art** | Generative art with p5.js |
| **mcp-builder** | Build MCP servers |
| **webapp-testing** | Test web apps with Playwright |
| **theme-factory** | Style artifacts with themes |
| **canvas-design** | Create visual art (PNG/PDF) |
| **brand-guidelines** | Anthropic brand styling |
| **slack-gif-creator** | Create animated GIFs for Slack |
| **internal-comms** | Write internal communications |
| **web-artifacts-builder** | Build HTML artifacts |
| **skill-creator** | Guide for creating new skills |
| **research-wbs-review** | Review WBS structures |

### Using Skills

List available skills:
```
You: skills
```

Activate a skill:
```
You: Activate the pdf skill to merge multiple PDFs
```

The agent automatically uses the appropriate skill based on your request and the skill's trigger conditions.

### Adding New Skills

1. Create a directory in `skills/`:
   ```bash
   mkdir skills/my-new-skill
   ```

2. Create `SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: my-new-skill
   description: Use this skill when...
   ---

   # My New Skill

   Documentation here...
   ```

3. Restart ChatAgent to load the new skill

See [SKILLS_GUIDE.md](SKILLS_GUIDE.md) for detailed documentation on creating and managing skills.

**Saving information:**
```
You: Remember that I prefer tabs over spaces for indentation

You: Save this API endpoint URL for future use
```

## Logging System

### Overview

ChatAgent automatically logs **all interactions with the LLM** to `chatagent.log`, providing complete visibility into requests and responses.

### What's Logged

- ✅ **Complete message content** - No truncation, full text recorded
- ✅ **All tool calls** - Function names and full arguments (formatted JSON)
- ✅ **Tool results** - Complete output from tool executions
- ✅ **Token usage** - Prompt, completion, and total tokens
- ✅ **Request metadata** - Model, temperature, timestamps
- ✅ **Response details** - Finish reason, full assistant replies

### Viewing Logs

```bash
# Real-time monitoring
tail -f chatagent.log

# View full log
cat chatagent.log

# Search for specific requests
grep "req_5" chatagent.log

# Find errors
grep "ERROR" chatagent.log
```

### Benefits

- **Debugging** - Track exactly what was sent and received
- **Cost Analysis** - Monitor token usage over time
- **Audit Trail** - Complete record of all interactions
- **Development** - Understand tool calling behavior

See [LOGGING.md](LOGGING.md) for complete documentation.

## Project Structure

```
chatagent/
├── main.py                  # Entry point
├── pyproject.toml          # Project configuration
├── .env                    # Configuration (create from .env.example)
├── .env.example            # Configuration template
├── README.md               # This file
└── chatagent/
    ├── __init__.py
    ├── cli.py              # CLI interface
    ├── agent.py            # Main agent logic
    ├── llm/
    │   ├── __init__.py
    │   └── client.py       # LLM client
    ├── tools/
    │   ├── __init__.py
    │   ├── base.py         # Tool base classes
    │   ├── file_ops.py     # File operation tools
    │   ├── search.py       # Search tools
    │   ├── shell.py        # Shell command tool
    │   ├── web.py          # Web tools
    │   ├── memory.py       # Memory tool
    │   ├── agents.py       # Agent tools
    │   └── skill.py        # Skill activation
    └── skills/
        ├── __init__.py
        └── manager.py      # Skills manager
```

## Advanced Usage

### Tool Usage

The agent automatically selects and uses appropriate tools based on your request. You can also explicitly request tool usage:

```
You: Use the glob tool to find all JavaScript files

You: Search for "function" in all Python files using search_file_content

You: Use the shell tool to check git status
```

### Memory System

The agent can save important information to memory:

```
You: Remember that this project uses Python 3.12

You: Save my preference for using black for code formatting

You: What do you remember about my preferences?
```

Memories are saved to `.chatagent_memory.json` in the current directory.

### Skills

Skills provide specialized capabilities for specific domains:

```
You: Activate the pdf skill
Assistant: [Activates PDF skill]

You: Now merge these three PDF files

You: Activate the xlsx skill to help me analyze sales data
```

## Development

### Adding New Tools

1. Create a new tool class in `chatagent/tools/`:
```python
from .base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Description of what this tool does"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Parameter description",
                }
            },
            "required": ["param1"],
        }

    def execute(self, param1: str) -> str:
        # Tool implementation
        return f"Result: {param1}"
```

2. Register the tool in `agent.py`:
```python
self.tools.register(MyTool())
```

### Adding New Skills

Skills are managed by the `SkillManager`. To add a new skill, update the `AVAILABLE_SKILLS` dictionary in `chatagent/skills/manager.py`.

## Troubleshooting

### API Key Issues
- Make sure your `.env` file exists and contains a valid API key
- Check that the API key has the correct permissions
- Verify the base URL is correct for your provider

### Connection Issues
- Check your internet connection
- Verify the API endpoint is accessible
- Check for firewall or proxy issues

### Tool Execution Errors
- Ensure you have necessary permissions for file operations
- Check file paths are correct and accessible
- For shell commands, verify the command is valid for your OS

## License

This project is open source. Feel free to use and modify as needed.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Acknowledgments

- Built with [OpenAI Python SDK](https://github.com/openai/openai-python)
- CLI interface powered by [Rich](https://github.com/Textualize/rich)
- Inspired by [Claude Code](https://github.com/anthropics/claude-code)
