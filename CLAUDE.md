# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Management

**Always use `uv` for package management**, not pip:

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add package-name

# Run Python scripts
uv run python script.py

# Run the CLI
uv run chatagent
# or
uv run python main.py
```

## Running and Testing

### Start the Agent

```bash
# Quick start
./run.sh

# Or directly
uv run chatagent

# Or via Python
uv run python main.py
```

### Run Tests

```bash
# Run all tests with pytest
uv run python -m pytest tests/

# Run a specific test file
uv run python tests/test_imports.py
uv run python tests/test_tool_confirmation.py
uv run python tests/test_readchar_confirmation.py
uv run python tests/test_date_in_prompt.py

# All test files are in tests/ directory
```

### Configuration

Copy and edit `.env` from `.env.example`:
```bash
cp .env.example .env
# Edit .env with your API key and settings
```

Required: `OPENAI_API_KEY`
Optional: `OPENAI_BASE_URL`, `OPENAI_MODEL`

## Architecture

### Three-Layer Design

ChatAgent uses a **Tool-Agent-CLI** architecture:

1. **CLI Layer** (`cli.py`): User interface with Rich, handles commands, manages session state (like `allow_all_tools`)
2. **Agent Layer** (`agent.py`): Orchestrates LLM, tools, skills, and conversation history
3. **Tool Layer** (`tools/`): Individual tool implementations following the Tool base class

```
User → CLI → Agent → LLM + Tools
                  ↓
            SkillManager (loads from skills/)
```

### Tool System

All tools inherit from `Tool` base class (`tools/base.py`):

```python
class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Description for LLM"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {...}  # JSON Schema

    @property
    def requires_confirmation(self) -> bool:
        return False  # True for dangerous operations

    def execute(self, **kwargs) -> str:
        return "Result"
```

**Tool Registration**: Tools are registered in `agent.py::_register_tools()`. The `ToolRegistry` converts them to OpenAI function calling format.

**Tool Confirmation**: Tools with `requires_confirmation=True` (Shell, Web, File Writing) pause execution and prompt user via `confirmation_callback` passed from CLI.

**Tools requiring confirmation:**
- `run_shell_command` - Shell command execution
- `web_fetch` - Fetch web content
- `google_web_search` - Web search
- `write_file` - File writing/overwriting (prevents data loss)

### Skills System

**Dynamic Loading**: Skills are auto-discovered from `skills/` directory. Each subdirectory contains:
- `SKILL.md` - Main file with YAML frontmatter (`name:`, `description:`)
- `reference/*.md` (optional) - Additional documentation loaded on-demand

**Skill Manager** (`skills/manager.py`):
- Parses YAML frontmatter from SKILL.md files
- Maintains `available_skills` dict (all skills)
- Maintains `active_skills` dict (currently activated)
- Injects active skill context into system prompt

**Activation**: Use `activate_skill` tool or `/skills` command. Active skills add their documentation to the system prompt.

### System Prompt Composition

The system prompt is dynamically built in `agent.py::_build_system_prompt()`:

1. **CHATAGENT.md** (if exists in cwd) - Project-specific instructions
2. **Agent Instructions** - Base ChatAgent capabilities
3. **Current Date/Time** - Auto-injected: `YYYY-MM-DD HH:MM:SS (Day)`
4. **Available Skills** - List with descriptions
5. **Active Skills Context** - Full documentation of activated skills

This composition happens on every `chat()` call to keep skills context fresh.

### Conversation Flow

```python
# agent.py::chat()
1. User message added to self.messages
2. System prompt built (includes CHATAGENT.md, date, skills)
3. LLM called with messages + tools
4. Loop (max 100 iterations):
   a. If tool_calls: execute each tool
      - Check requires_confirmation
      - Call confirmation_callback if needed
      - Execute tool or cancel based on response
   b. Add tool results to messages
   c. Call LLM again with updated messages
   d. If no tool_calls: return final response
```

### Logging System

**Complete LLM interaction logging** to `chatagent.log`:
- Every request/response (full content, no truncation)
- All tool calls with formatted JSON arguments
- Tool results
- Token usage
- Timestamps

Logger is in `llm/client.py`. To debug tool execution or LLM behavior, check this log file.

### CLI Commands

User commands (start with `/`):
- `/clear` - Clears history AND resets `allow_all_tools` to False
- `/reset-confirm` - Resets `allow_all_tools` only (keeps history)
- `/status` - Shows message count, model, active skills, confirmation mode
- `/model [name]` - List models or switch to specified model
- `/skills` - List available/active skills
- `/memory` - Show saved memories
- `/help` - Show help

Session state `allow_all_tools` persists across tool confirmations within one session.

## Adding New Components

### Adding a Tool

1. Create tool class in `chatagent/tools/<module>.py`
2. Implement `Tool` interface (name, description, parameters, execute)
3. Set `requires_confirmation=True` if dangerous:
   - Shell commands (arbitrary execution)
   - Web access (network requests, privacy)
   - File writing/overwriting (data loss risk)
   - File deletion (irreversible)
4. Register in `agent.py::_register_tools()`:
   ```python
   from .tools.mymodule import MyTool
   # In _register_tools():
   tools_to_register.append(MyTool())
   ```

### Adding a Skill

1. Create directory: `skills/my-skill/`
2. Create `SKILL.md` with YAML frontmatter:
   ```yaml
   ---
   name: my-skill
   description: Use when... (trigger conditions)
   ---

   # Skill Documentation
   ...
   ```
3. (Optional) Add `reference/*.md` files for on-demand loading
4. Restart agent - skill auto-discovered

Reference files are loaded only when skill is activated (saves memory).

## Important Patterns

### Confirmation Callback Pattern

CLI creates callback and passes to Agent:
```python
# cli.py
def confirm_tool_execution(self, name, desc, args) -> bool:
    # Show menu, get user choice
    # Return True/False

self.agent = ChatAgent(
    confirmation_callback=self.confirm_tool_execution
)
```

Agent checks before tool execution:
```python
# agent.py
if tool.requires_confirmation and self.confirmation_callback:
    confirmed = self.confirmation_callback(name, desc, args)
    if not confirmed:
        result = "Tool execution cancelled by user"
```

### Single-Key Input

Uses `readchar` library for instant response:
```python
import readchar
key = readchar.readkey()  # No Enter needed
```

Supports: `1`, `2`, `3`, `Esc`, `Ctrl+C`. Invalid keys are silently ignored.

### Memory System

Persistent JSON storage in `.chatagent_memory.json` (gitignored):
```python
# tools/memory.py
{"key": {"value": "...", "tags": [...], "timestamp": "..."}}
```

Accessible via `save_memory` tool.

## File Organization

```
chatagent/
├── chatagent/           # Main package
│   ├── agent.py        # Core orchestration
│   ├── cli.py          # CLI interface with Rich
│   ├── llm/
│   │   └── client.py   # OpenAI client wrapper
│   ├── tools/          # Tool implementations
│   │   ├── base.py     # Tool base class + registry
│   │   ├── file_ops.py # Read, write, edit, list
│   │   ├── search.py   # Glob, grep
│   │   ├── shell.py    # Shell execution
│   │   ├── web.py      # Fetch, search
│   │   ├── memory.py   # Persistent memory
│   │   ├── agents.py   # Helper agents
│   │   └── skill.py    # Skill activation
│   └── skills/
│       └── manager.py  # Skill loading + management
├── skills/             # Skill definitions (SKILL.md files)
├── tests/              # Test files (test_*.py)
├── docs/               # Documentation
│   ├── features/       # Feature documentation
│   ├── updates/        # Update logs
│   ├── implementation/ # Technical implementation details
│   └── dev-notes/      # Development notes (archived)
├── CLAUDE.md           # Claude Code guidance
├── CHATAGENT.md        # Project-specific instructions
└── main.py            # Entry point
```

## Key Dependencies

- `openai` - LLM client (OpenAI-compatible APIs)
- `rich` - CLI interface (markdown, panels, prompts)
- `readchar` - Single-key input (no Enter needed)
- `httpx` - HTTP client for web tools
- `beautifulsoup4` - HTML parsing
- `python-dotenv` - Environment configuration
