# ChatAgent - Quick Start Guide

Get up and running with ChatAgent in under 2 minutes!

## 1. Setup Environment

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` and add your API key:
```env
OPENAI_API_KEY=your-api-key-here
```

## 2. Install Dependencies (uv)

```bash
# Sync dependencies - this creates a virtual environment and installs everything
uv sync
```

That's it! No need to manually create virtual environments or install packages one by one.

## 3. Run ChatAgent

```bash
# Method 1: Direct run with uv
uv run python main.py

# Method 2: Use the convenience script
./run.sh

# Method 3: Use the installed command
uv run chatagent
```

## 4. Try It Out!

Once running, try these commands:

```
You: /help
```
Shows all available commands and features.

```
You: Read the file README.md
```
The agent will use the `read_file` tool to read and display the file.

```
You: Search for all Python files in this directory
```
The agent will use the `glob` tool to find all `.py` files.

```
You: /skills
```
Shows all available Claude skills.

```
You: Remember that I prefer using uv for Python projects
```
Saves this preference to memory using the `save_memory` tool.

## Common Commands

All commands start with `/`:

- `/help` - Show help message
- `/model` - List or switch models
  - `/model` - Show current and available models
  - `/model gpt-4` - Switch to GPT-4
  - `/model claude-sonnet-4-5` - Switch to Claude Sonnet
- `/clear` - Clear conversation history
- `/status` - Show conversation status (includes current model)
- `/skills` - List available skills
- `/memory` - Show saved memories
- `/exit` or `/quit` - Exit the program

**Note:** Regular messages (without `/`) are sent to the AI agent.

## Example Workflows

### Working with Files
```
You: Create a new file called test.py with a hello world function
You: Read the file test.py
You: Replace the hello function with a greeting function that takes a name
```

### Web Research
```
You: Search for Python async best practices
You: Fetch the content from the first result
```

### Using Skills
```
You: Activate the pdf skill
You: Now help me merge multiple PDFs
```

### Using Commands
```
You: /model              (show current model and available models)
You: /model gpt-4        (switch to GPT-4)
You: /skills             (list all skills)
You: /memory             (show memories)
You: /status             (show status and current model)
You: /clear              (clear history)
```

### Code Analysis
```
You: Find all TODO comments in Python files
You: Search for function definitions in the utils module
You: Use the codebase investigator to analyze the project structure
```

## Tips

1. **Be specific**: The more specific your request, the better the agent can help you.

2. **Use tools naturally**: Just ask in natural language - the agent will figure out which tools to use.

3. **Check memory**: Use the `/memory` command to see what the agent has remembered about your preferences.

4. **Activate skills**: For specialized tasks (PDFs, spreadsheets, etc.), activate the relevant skill first.

5. **Multi-turn conversations**: The agent remembers context, so you can build on previous responses.

6. **Commands vs messages**: Start with `/` for commands, anything else is sent to the AI agent.

## Troubleshooting

**Problem**: `command not found: uv`
**Solution**: Install uv first: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Problem**: API key error
**Solution**: Make sure `.env` file exists and contains a valid `OPENAI_API_KEY`

**Problem**: Tool execution fails
**Solution**: Check file permissions and paths. Use absolute paths if relative paths don't work.

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the different tools available with the `help` command
- Try activating different skills with the `skills` command
- Save your preferences with the `save_memory` tool

Enjoy using ChatAgent! 🚀
