"""Test that skills are included in system prompt."""

import os
from dotenv import load_dotenv
from chatagent import ChatAgent

def test_skills_in_system_prompt():
    """Test that available skills are listed in the system prompt."""
    load_dotenv()

    agent = ChatAgent(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_MODEL"),
    )

    print("Testing Skills in System Prompt")
    print("=" * 80)

    # Build system prompt
    system_prompt = agent._build_system_prompt()

    print("\n=== SYSTEM PROMPT ===")
    print(system_prompt)
    print("\n" + "=" * 80)

    # Check if skills section exists
    if "=== Available Skills ===" in system_prompt:
        print("✅ Skills section found in system prompt")
    else:
        print("❌ Skills section NOT found in system prompt")

    # List available skills
    skills = agent.skill_manager.list_available_skills()
    print(f"\n✅ Found {len(skills)} available skills")

    # Check if each skill is mentioned in the prompt
    print("\n=== Skills Verification ===")
    for skill_name in sorted(skills):
        if skill_name in system_prompt:
            print(f"✅ {skill_name} - found in prompt")
        else:
            print(f"❌ {skill_name} - NOT found in prompt")

    # Test activating a skill and rebuilding prompt
    print("\n=== Testing Skill Activation ===")
    if "pdf" in skills:
        result = agent.skill_manager.activate_skill("pdf", "Test task")
        print(f"Activated PDF skill: {result[:100]}...")

        # Rebuild system prompt after activation
        system_prompt_after = agent._build_system_prompt()

        if "=== Active Skills ===" in system_prompt_after:
            print("✅ Active skills section found after activation")
        else:
            print("❌ Active skills section NOT found after activation")
    else:
        print("⚠️  PDF skill not available for activation test")

    return system_prompt

if __name__ == "__main__":
    test_skills_in_system_prompt()
