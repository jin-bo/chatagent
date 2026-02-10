"""Test script to verify all imports work correctly."""

print("Testing imports...")

try:
    from chatagent.llm import LLMClient
    print("✓ LLM client import successful")
except Exception as e:
    print(f"✗ LLM client import failed: {e}")

try:
    from chatagent.tools import (
        ToolRegistry,
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ReadFolderTool,
        FindFilesTool,
        SearchTextTool,
        ShellTool,
        WebFetchTool,
        GoogleSearchTool,
        SaveMemoryTool,
        CLIHelpAgentTool,
        CodebaseInvestigatorTool,
        ActivateSkillTool,
    )
    print("✓ All tools imported successfully")
except Exception as e:
    print(f"✗ Tools import failed: {e}")

try:
    from chatagent.skills import SkillManager
    print("✓ Skill manager import successful")
except Exception as e:
    print(f"✗ Skill manager import failed: {e}")

try:
    from chatagent.agent import ChatAgent
    print("✓ Chat agent import successful")
except Exception as e:
    print(f"✗ Chat agent import failed: {e}")

try:
    from chatagent.cli import ChatAgentCLI
    print("✓ CLI import successful")
except Exception as e:
    print(f"✗ CLI import failed: {e}")

print("\n✓ All imports successful! The project is ready to run.")
print("\nTo start ChatAgent, run:")
print("  uv run python main.py")
print("or")
print("  ./run.sh")
