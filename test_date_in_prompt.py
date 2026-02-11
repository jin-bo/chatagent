"""Test that current date is included in system prompt."""

from datetime import datetime
from unittest.mock import Mock, patch


def test_date_in_system_prompt():
    """Test that system prompt includes current date information."""

    # Mock the LLMClient
    with patch('chatagent.agent.LLMClient') as mock_llm_client:
        mock_logger = Mock()
        mock_llm_client.return_value.logger = mock_logger
        mock_llm_client.return_value.model = "gpt-4"

        from chatagent.agent import ChatAgent

        # Create agent
        agent = ChatAgent()

        # Get system prompt
        system_prompt = agent._build_system_prompt()

        # Check that it contains date information
        assert "Current Date and Time:" in system_prompt, "System prompt should contain 'Current Date and Time:'"

        # Check format - should contain year
        now = datetime.now()
        current_year = str(now.year)
        assert current_year in system_prompt, f"System prompt should contain current year {current_year}"

        # Check that day of week is present
        day_of_week = now.strftime("%A")
        assert day_of_week in system_prompt, f"System prompt should contain day of week: {day_of_week}"

        print(f"✅ System prompt includes current date: {now.strftime('%Y-%m-%d %H:%M:%S')} ({day_of_week})")

        # Print a snippet of the prompt to verify
        lines = system_prompt.split('\n')
        for i, line in enumerate(lines):
            if "Current Date and Time:" in line:
                print(f"✅ Date line found: {line}")
                break


def test_date_format():
    """Test that date is formatted correctly."""

    with patch('chatagent.agent.LLMClient') as mock_llm_client:
        mock_logger = Mock()
        mock_llm_client.return_value.logger = mock_logger
        mock_llm_client.return_value.model = "gpt-4"

        from chatagent.agent import ChatAgent

        agent = ChatAgent()
        system_prompt = agent._build_system_prompt()

        # Check date format: YYYY-MM-DD HH:MM:SS
        import re
        date_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(date_pattern, system_prompt), "System prompt should contain date in format YYYY-MM-DD HH:MM:SS"

        print("✅ Date format is correct (YYYY-MM-DD HH:MM:SS)")


def test_date_with_project_instructions():
    """Test that date is included even with project instructions."""

    with patch('chatagent.agent.LLMClient') as mock_llm_client:
        mock_logger = Mock()
        mock_llm_client.return_value.logger = mock_logger
        mock_llm_client.return_value.model = "gpt-4"

        from chatagent.agent import ChatAgent

        # Create agent (should load CHATAGENT.md if it exists)
        agent = ChatAgent()

        # Get system prompt
        system_prompt = agent._build_system_prompt()

        # Check that date is present
        assert "Current Date and Time:" in system_prompt, "Date should be present even with project instructions"

        # Check if project instructions are loaded
        if agent.project_instructions:
            assert "=== Project Instructions ===" in system_prompt
            print("✅ Date included with project instructions")
        else:
            print("✅ Date included without project instructions")


if __name__ == "__main__":
    print("Testing date in system prompt...")
    print()

    try:
        test_date_in_system_prompt()
        print()
        test_date_format()
        print()
        test_date_with_project_instructions()
        print()
        print("=" * 50)
        print("✅ All tests passed!")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
