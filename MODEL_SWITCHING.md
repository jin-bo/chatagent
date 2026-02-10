# Model Switching Guide

## Overview

ChatAgent supports switching between different LLM models during a conversation using the `/model` command.

## Usage

### Show Current Model and Available Models

```bash
You: /model
```

Output:
```
Current Model: claude-sonnet-4-5

Available Models:

  Claude:
    • claude-opus-4
    • claude-sonnet-4-5 ✓
    • claude-sonnet-4
    • claude-haiku-4

  OpenAI GPT:
    • gpt-4-turbo-preview
    • gpt-4-turbo
    • gpt-4
    • gpt-4-32k
    • gpt-3.5-turbo
    • gpt-3.5-turbo-16k

  Other:
    • deepseek-chat
    • deepseek-coder

Usage: /model <model_name>
Example: /model claude-sonnet-4-5
```

### Switch to a Specific Model

```bash
You: /model gpt-4
```

Output:
```
Model changed from claude-sonnet-4-5 to gpt-4
```

### Check Current Model in Status

```bash
You: /status
```

Output includes current model:
```
Total messages: 10
Current model: gpt-4
Active skills: 0
```

## Available Models

### Claude Models

| Model | Description |
|-------|-------------|
| `claude-opus-4` | Most capable Claude model |
| `claude-sonnet-4-5` | Balanced performance and speed (default) |
| `claude-sonnet-4` | Previous Sonnet version |
| `claude-haiku-4` | Fastest Claude model |

### OpenAI GPT Models

| Model | Description |
|-------|-------------|
| `gpt-4-turbo-preview` | Latest GPT-4 Turbo |
| `gpt-4-turbo` | GPT-4 Turbo with vision |
| `gpt-4` | Standard GPT-4 |
| `gpt-4-32k` | GPT-4 with 32K context |
| `gpt-3.5-turbo` | Fast and cost-effective |
| `gpt-3.5-turbo-16k` | GPT-3.5 with 16K context |

### Other Models

| Model | Description |
|-------|-------------|
| `deepseek-chat` | DeepSeek chat model |
| `deepseek-coder` | DeepSeek code-focused model |

## Use Cases

### Compare Model Responses

Switch between models to compare their responses to the same question:

```bash
You: /model gpt-4
You: Explain quantum computing in simple terms
[GPT-4 response]

You: /model claude-sonnet-4-5
You: Explain quantum computing in simple terms
[Claude response]
```

### Use Appropriate Model for Task

Switch to the most suitable model for your task:

```bash
# Use a powerful model for complex reasoning
You: /model claude-opus-4
You: Analyze this complex algorithm...

# Use a faster model for simple tasks
You: /model claude-haiku-4
You: Format this text...

# Use GPT-4 for tasks it excels at
You: /model gpt-4
You: Generate creative content...
```

### Cost Optimization

Use cheaper models when appropriate:

```bash
# Use faster/cheaper model for simple queries
You: /model gpt-3.5-turbo
You: What's the weather?

# Switch to more capable model for complex tasks
You: /model gpt-4
You: Help me debug this complex issue...
```

## Features

### Session Persistence

The model setting persists throughout your session:
- All subsequent messages use the selected model
- Model choice is maintained until you switch again
- Shown in welcome message and status

### Logging

All model switches are logged to `chatagent.log`:
```
2026-02-09 14:30:45 - chatagent.llm - INFO - Model changed from claude-sonnet-4-5 to gpt-4
```

### Context Preservation

Switching models does NOT clear conversation history:
- Previous messages remain in context
- The new model sees the full conversation
- Continue seamlessly with different models

## Configuration

### Default Model

Set the default model via environment variable:

```bash
# In .env file
OPENAI_MODEL=claude-sonnet-4-5
```

Or when initializing:

```python
from chatagent import ChatAgent

agent = ChatAgent(model="gpt-4")
```

### API Configuration

Ensure your API key and base URL support the models you want to use:

```bash
# For OpenAI models
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1

# For Claude via OpenRouter or similar
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://openrouter.ai/api/v1

# For custom endpoints
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://your-endpoint.com/v1
```

## Examples

### Basic Model Switching

```bash
# Start with default model
$ uv run python main.py

You: /model
> Current Model: claude-sonnet-4-5

You: Hello
> [Response from Claude Sonnet]

You: /model gpt-4
> Model changed from claude-sonnet-4-5 to gpt-4

You: Hello again
> [Response from GPT-4]
```

### Comparing Models

```bash
You: /model claude-opus-4
You: Write a poem about AI

You: /model gpt-4
You: Write a poem about AI

You: /model claude-haiku-4
You: Write a poem about AI
```

### Task-Specific Models

```bash
# Use DeepSeek for coding tasks
You: /model deepseek-coder
You: Optimize this Python function...

# Switch to Claude for analysis
You: /model claude-sonnet-4-5
You: Explain what this code does...
```

## Best Practices

1. **Choose Wisely**: Select models based on task complexity
   - Simple tasks → Faster/cheaper models
   - Complex tasks → More capable models

2. **Check Availability**: Ensure your API supports the model
   - Not all endpoints support all models
   - Check documentation for your provider

3. **Monitor Costs**: Different models have different pricing
   - GPT-4 is more expensive than GPT-3.5
   - Claude Opus is more expensive than Haiku

4. **Test Responses**: Compare model outputs for important tasks
   - Different models have different strengths
   - Use `/model` to switch and compare easily

5. **Use Status**: Check current model regularly
   - Use `/status` to see which model is active
   - Avoid confusion about which model is responding

## Troubleshooting

### Model Not Available

If you switch to a model that's not supported by your API:

```bash
You: /model some-unavailable-model
> Model changed from claude-sonnet-4-5 to some-unavailable-model
[Next API call will fail with error]
```

**Solution**: Only use models supported by your API endpoint.

### API Key Issues

If your API key doesn't support the model:
- Check your API provider's documentation
- Verify your subscription/plan includes the model
- Use a different endpoint if needed

### Model List Outdated

The built-in model list may not include all available models.

**Solution**: You can still use any model name:
```bash
You: /model your-custom-model-name
```

## Advanced Usage

### Custom Models

You can switch to any model name, even if not in the list:

```bash
You: /model my-custom-model
> Model changed from claude-sonnet-4-5 to my-custom-model
```

This is useful for:
- Custom fine-tuned models
- New models not yet in the list
- Provider-specific model names

### Programmatic Access

```python
from chatagent import ChatAgent

agent = ChatAgent()

# Get current model
current = agent.get_current_model()
print(f"Current: {current}")

# List available models
models = agent.list_available_models()
print(f"Available: {models}")

# Switch model
result = agent.set_model("gpt-4")
print(result)
```

## Model Comparison Table

| Feature | Claude Opus | Claude Sonnet | Claude Haiku | GPT-4 | GPT-3.5 |
|---------|-------------|---------------|--------------|-------|---------|
| Speed | Medium | Fast | Very Fast | Medium | Very Fast |
| Capability | Highest | High | Medium | Highest | Medium |
| Cost | Highest | Medium | Lowest | High | Low |
| Context | Large | Large | Medium | Large | Medium |
| Best For | Complex reasoning | Balanced tasks | Simple queries | Creative tasks | Quick responses |

## FAQ

**Q: Does switching models clear my conversation history?**
A: No, conversation history is preserved when switching models.

**Q: Can I use models not in the list?**
A: Yes, you can specify any model name. It will be used if your API supports it.

**Q: Which model is best?**
A: It depends on your task. Use powerful models for complex tasks, faster models for simple ones.

**Q: How do I know which model I'm using?**
A: Use `/model` (no arguments) or `/status` to see the current model.

**Q: Can I set a default model?**
A: Yes, set `OPENAI_MODEL` in your `.env` file.

**Q: Are all models available with all API providers?**
A: No, availability depends on your API provider. Check their documentation.

---

**Last Updated**: 2026-02-09
**Feature Status**: ✅ Available
**Command**: `/model [model_name]`
