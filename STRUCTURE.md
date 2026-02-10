# Project Structure

```
chatagent/
│
├── 📄 Configuration Files
│   ├── .env.example              # Environment configuration template
│   ├── .gitignore                # Git ignore rules
│   ├── .python-version           # Python 3.12
│   └── pyproject.toml            # Project metadata & dependencies
│
├── 📄 Documentation
│   ├── README.md                 # Full documentation (detailed)
│   ├── QUICKSTART.md             # Quick start guide (2 minutes)
│   ├── PROJECT_SUMMARY.md        # Architecture & implementation details
│   └── STRUCTURE.md              # This file
│
├── 🚀 Entry Points
│   ├── main.py                   # Main entry point
│   └── run.sh                    # Convenience script (uv run)
│
├── 🧪 Testing
│   └── test_imports.py           # Import verification test
│
└── 📦 chatagent/ (Main Package)
    │
    ├── __init__.py               # Package initialization
    │
    ├── 🎯 Core Modules
    │   ├── cli.py                # Rich-based CLI interface
    │   └── agent.py              # Main agent orchestration
    │
    ├── 🤖 LLM Module
    │   └── llm/
    │       ├── __init__.py
    │       └── client.py         # OpenAI-compatible LLM client
    │
    ├── 🛠️  Tools Module (13 Tools)
    │   └── tools/
    │       ├── __init__.py       # Tool exports
    │       ├── base.py           # Tool base class & registry
    │       ├── file_ops.py       # 4 tools: read, write, replace, list
    │       ├── search.py         # 2 tools: glob, search_file_content
    │       ├── shell.py          # 1 tool: run_shell_command
    │       ├── web.py            # 2 tools: web_fetch, google_web_search
    │       ├── memory.py         # 1 tool: save_memory
    │       ├── agents.py         # 2 tools: cli_help, codebase_investigator
    │       └── skill.py          # 1 tool: activate_skill
    │
    └── 🎯 Skills Module
        └── skills/
            ├── __init__.py       # Skills exports
            └── manager.py        # Skills manager (16 skills)

Generated Files (gitignored):
├── .venv/                        # Virtual environment (created by uv)
└── .chatagent_memory.json        # Memory storage (created at runtime)
```

## Module Descriptions

### Core (2 files)
- **cli.py** (200 lines) - Beautiful CLI with Rich, commands, status display
- **agent.py** (180 lines) - Orchestrates LLM, tools, skills, conversation

### LLM (1 file)
- **client.py** (70 lines) - OpenAI client wrapper with tool support

### Tools (8 files)
- **base.py** (80 lines) - Tool interface, registry pattern
- **file_ops.py** (170 lines) - File operations with safety checks
- **search.py** (140 lines) - File finding and content search with regex
- **shell.py** (60 lines) - Shell execution with timeout
- **web.py** (160 lines) - Web fetching and search (DuckDuckGo)
- **memory.py** (100 lines) - JSON-based memory with timestamps
- **agents.py** (120 lines) - Specialized helper agents
- **skill.py** (40 lines) - Skill activation interface

### Skills (1 file)
- **manager.py** (110 lines) - Manages 16 Claude skills

## Statistics

- **Total Python files**: 18
- **Total lines of code**: ~1,700
- **Tools implemented**: 13/13 ✅
- **Skills supported**: 16
- **Dependencies**: 24 packages
- **Python version**: 3.12+

## File Sizes (approximate)

```
Total:     ~50 KB Python source
Config:    ~5 KB
Docs:      ~25 KB
Tests:     ~2 KB
```

## Key Design Decisions

1. **Modular structure** - Each tool in its own logical group
2. **Base classes** - Common interface for all tools
3. **Registry pattern** - Dynamic tool discovery and execution
4. **OpenAI compatibility** - Works with any OpenAI-compatible API
5. **Rich CLI** - Beautiful, modern terminal interface
6. **uv support** - Fast, modern Python package management
7. **Memory system** - Persistent context across sessions
8. **Skills integration** - Claude Code compatibility

## Import Graph

```
main.py
  └── cli.py
       └── agent.py
            ├── llm/client.py
            ├── tools/*
            └── skills/manager.py
```

## Data Flow

```
User Input (CLI)
    ↓
ChatAgent.chat()
    ↓
LLMClient.chat() + tools
    ↓
Tool execution (if needed)
    ↓
Final response
    ↓
Display to user (Rich)
```
