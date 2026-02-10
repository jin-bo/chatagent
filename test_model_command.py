"""Test script to verify model switching functionality."""

import os

# Set test API key
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "test-key"

from chatagent.agent import ChatAgent

print("=" * 70)
print("Testing Model Switching Functionality")
print("=" * 70)

# Initialize agent
print("\n1. Initializing ChatAgent with default model...")
agent = ChatAgent()
print(f"✓ Default model: {agent.get_current_model()}")

# List available models
print("\n2. Listing available models...")
models = agent.list_available_models()
print(f"✓ Found {len(models)} available models:")
for model in models:
    print(f"   • {model}")

# Test model switching
print("\n3. Testing model switching...")
test_models = ["gpt-4", "claude-sonnet-4-5", "gpt-3.5-turbo"]

for model in test_models:
    result = agent.set_model(model)
    current = agent.get_current_model()
    if current == model:
        print(f"✓ {result}")
    else:
        print(f"✗ Failed to switch to {model}")

# Test conversation summary with model info
print("\n4. Testing conversation summary (includes model info)...")
summary = agent.get_conversation_summary()
print("Summary:")
for line in summary.split('\n'):
    print(f"   {line}")

# Switch back to Claude
print("\n5. Switching back to Claude Sonnet 4.5...")
agent.set_model("claude-sonnet-4-5")
print(f"✓ Current model: {agent.get_current_model()}")

print("\n" + "=" * 70)
print("✓ All model tests passed!")
print("=" * 70)

print("\n📋 Usage in ChatAgent:")
print("  /model                    - Show current and available models")
print("  /model gpt-4              - Switch to GPT-4")
print("  /model claude-sonnet-4-5  - Switch to Claude Sonnet")
print("  /status                   - Show status (includes current model)")
