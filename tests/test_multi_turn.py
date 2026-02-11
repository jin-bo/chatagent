"""Test multi-turn tool calls."""

import os
from dotenv import load_dotenv
from chatagent import ChatAgent

def test_multi_turn_tool_calls():
    """Test that agent can handle multiple rounds of tool calls."""
    load_dotenv()

    agent = ChatAgent(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_MODEL"),
    )

    print("Testing multi-turn tool calls...")
    print("=" * 80)

    # This should trigger multiple tool calls:
    # 1. List directory to see what's there
    # 2. Read some files
    # 3. Possibly more operations
    response = agent.chat("List the contents of the skills directory and tell me about one of the skills")

    print("\nResponse:")
    print(response)
    print("=" * 80)
    print(f"\nTotal messages in history: {len(agent.messages)}")

    # Count tool messages
    tool_messages = [m for m in agent.messages if m.get('role') == 'tool']
    print(f"Tool calls executed: {len(tool_messages)}")

    return response

if __name__ == "__main__":
    test_multi_turn_tool_calls()
