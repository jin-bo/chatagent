# ChatAgent Documentation

This directory contains documentation for the ChatAgent project.

## Structure

### Core Documentation

User-facing guides and references:

- [LOGGING.md](LOGGING.md) - Complete logging system documentation
- [MODEL_SWITCHING.md](MODEL_SWITCHING.md) - Guide to switching between LLM models
- [SKILLS_GUIDE.md](SKILLS_GUIDE.md) - Skills system guide and how to create skills
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide (2-minute setup)
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick reference for common tasks
- [DEMO.md](DEMO.md) - Interactive demo walkthrough

### `/features` - Feature Documentation
Detailed documentation for major features, including design decisions and implementation details:

- [CHATAGENT_MD_FEATURE.md](features/CHATAGENT_MD_FEATURE.md) - CHATAGENT.md auto-loading for project-specific instructions
- [TOOL_CONFIRMATION_FEATURE.md](features/TOOL_CONFIRMATION_FEATURE.md) - User confirmation system for Shell & Web tools
- [DATE_CONTEXT_FEATURE.md](features/DATE_CONTEXT_FEATURE.md) - Current date/time injection in system prompt

### `/updates` - Update Logs
Detailed change logs for specific updates:

- [SKILLS_UPDATE.md](updates/SKILLS_UPDATE.md) - Skills system enhancements
- [LOGGING_UPDATE.md](updates/LOGGING_UPDATE.md) - Logging improvements
- [COMMANDS_UPDATE.md](updates/COMMANDS_UPDATE.md) - CLI commands updates
- [MODEL_COMMAND_UPDATE.md](updates/MODEL_COMMAND_UPDATE.md) - Model switching command
- [SKILLS_PROMPT_UPDATE.md](updates/SKILLS_PROMPT_UPDATE.md) - Skills prompt integration
- [MENU_CONFIRMATION_UPDATE.md](updates/MENU_CONFIRMATION_UPDATE.md) - Menu-based confirmation system

### `/implementation` - Technical Implementation Details
Deep dives into implementation specifics for developers:

- [READCHAR_IMPLEMENTATION.md](implementation/READCHAR_IMPLEMENTATION.md) - Single-key input with readchar library
- [CLEAR_RESETS_CONFIRMATION.md](implementation/CLEAR_RESETS_CONFIRMATION.md) - /clear command confirmation reset
- [TOOL_CONFIRMATION.md](implementation/TOOL_CONFIRMATION.md) - Tool confirmation mechanism details

### `/dev-notes` - Development Notes
Historical development notes and summaries (archived):

- [FIXES_SUMMARY.md](dev-notes/FIXES_SUMMARY.md) - Summary of fixes
- [MULTI_TURN_FIX.md](dev-notes/MULTI_TURN_FIX.md) - Multi-turn conversation fix details
- [SESSION_SUMMARY.md](dev-notes/SESSION_SUMMARY.md) - Session improvement summary
- [PROJECT_SUMMARY.md](dev-notes/PROJECT_SUMMARY.md) - Project summary
- [STRUCTURE.md](dev-notes/STRUCTURE.md) - Project structure notes

## Main Documentation

For general project information, see:
- [README.md](../README.md) - Project overview and quick start
- [CLAUDE.md](../CLAUDE.md) - Guidance for Claude Code when working with this codebase

## Contributing

When adding new features or making significant changes:
1. Document the feature in `/features` if it's a major addition
2. Add update notes in `/updates` for specific changes
3. Update the main README.md with user-facing information
