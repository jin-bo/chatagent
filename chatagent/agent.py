"""Main agent logic for ChatAgent."""

import json
from typing import Any, Dict, List, Optional

from .llm import LLMClient
from .tools import (
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
from .skills import SkillManager


class ChatAgent:
    """Main chat agent with tool and skill support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize chat agent.

        Args:
            api_key: API key for LLM service
            base_url: Base URL for API endpoint
            model: Model name to use
        """
        self.llm = LLMClient(api_key=api_key, base_url=base_url, model=model)
        self.skill_manager = SkillManager()
        self.memory_tool = SaveMemoryTool()

        # Initialize tool registry
        self.tools = ToolRegistry()
        self._register_tools()

        # Conversation history
        self.messages: List[Dict[str, Any]] = []

    def _register_tools(self):
        """Register all available tools."""
        tools_to_register = [
            ReadFileTool(),
            WriteFileTool(),
            EditTool(),
            ReadFolderTool(),
            FindFilesTool(),
            SearchTextTool(),
            ShellTool(),
            WebFetchTool(),
            GoogleSearchTool(),
            self.memory_tool,
            CLIHelpAgentTool(),
            CodebaseInvestigatorTool(),
            ActivateSkillTool(self.skill_manager),
        ]

        for tool in tools_to_register:
            self.tools.register(tool)

    def _build_system_prompt(self) -> str:
        """Build system prompt for the agent.

        Returns:
            System prompt string
        """
        prompt = """You are ChatAgent, a helpful AI assistant with access to various tools and skills.

You can help users with:
- Reading, writing, and editing files
- Searching for files and text content
- Executing shell commands
- Fetching web content and searching the web
- Saving important information to memory
- Activating specialized skills for specific tasks
- Investigating codebases and project structures

When users ask you to do something:
1. Think about which tools would be helpful
2. Use the appropriate tools to complete the task
3. Provide clear and concise responses
4. If you need more information, ask the user

Be proactive in using tools when they would be helpful. For example:
- If asked about a file, use read_file to view it
- If asked to search for something in code, use search_file_content
- If asked to create or modify files, use write_file or replace
- If asked to fetch web content, use web_fetch
- For specialized tasks, check if there's an appropriate skill to activate

Always be helpful, accurate, and efficient."""

        # Add available skills section
        available_skills = self.skill_manager.list_available_skills()
        if available_skills:
            prompt += "\n\n=== Available Skills ===\n"
            prompt += "You have access to specialized skills. Use the 'activate_skill' tool to activate them when needed.\n\n"

            for skill_name in sorted(available_skills):
                skill_info = self.skill_manager.get_skill_info(skill_name)
                if skill_info:
                    description = skill_info.get('description', 'No description available')
                    prompt += f"• {skill_name}: {description}\n"

            prompt += "\nWhen the user's request matches a skill's description, use the activate_skill tool before proceeding with the task."

        # Add active skills context if any
        skills_context = self.skill_manager.get_skills_context()
        if skills_context:
            prompt += "\n\n" + skills_context

        return prompt

    def add_message(self, role: str, content: str):
        """Add a message to conversation history.

        Args:
            role: Message role (user/assistant/system)
            content: Message content
        """
        self.messages.append({"role": role, "content": content})

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []

    def chat(self, user_message: str, max_iterations: int = 100) -> str:
        """Process user message and generate response.

        Args:
            user_message: User's message
            max_iterations: Maximum number of tool call iterations to prevent infinite loops

        Returns:
            Assistant's response
        """
        # Add user message
        self.add_message("user", user_message)

        # Build system prompt (dynamically to include active skills)
        system_prompt = self._build_system_prompt()

        # Prepare messages with system prompt
        messages_with_system = [
            {"role": "system", "content": system_prompt}
        ] + self.messages

        # Get tools in OpenAI format
        tools = self.tools.to_openai_format()

        # Call LLM and handle multiple rounds of tool calls
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            self.llm.logger.info(f"LLM iteration {iteration}/{max_iterations}")

            # Call LLM
            response = self.llm.chat(messages=messages_with_system, tools=tools)

            # Process response
            assistant_message = response.choices[0].message

            # Check if tool calls are needed
            if assistant_message.tool_calls:
                self.llm.logger.info(f"Processing {len(assistant_message.tool_calls)} tool call(s) in iteration {iteration}")
                # Add assistant message with tool calls
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                })

                # Execute tool calls
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # Execute tool
                    try:
                        tool = self.tools.get(function_name)
                        result = tool.execute(**function_args)
                    except Exception as e:
                        result = f"Error executing {function_name}: {str(e)}"

                    # Add tool result to messages
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": result,
                    })

                # Update messages for next iteration
                # Rebuild system prompt in case skills were activated
                system_prompt = self._build_system_prompt()
                messages_with_system = [
                    {"role": "system", "content": system_prompt}
                ] + self.messages

                # Continue loop to check if more tool calls are needed
            else:
                # No more tool calls, we have the final response
                self.llm.logger.info(f"Reached final response in iteration {iteration}")
                assistant_content = assistant_message.content or ""
                self.add_message("assistant", assistant_content)
                return assistant_content

        # If we hit max iterations, return what we have
        self.llm.logger.warning(f"Maximum tool call iterations ({max_iterations}) reached")
        assistant_content = assistant_message.content or "Maximum tool call iterations reached."
        self.add_message("assistant", assistant_content)
        return assistant_content

    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation.

        Returns:
            Conversation summary
        """
        if not self.messages:
            return "No conversation history"

        summary = f"Total messages: {len(self.messages)}\n"
        summary += f"Current model: {self.llm.model}\n"
        summary += f"Active skills: {len(self.skill_manager.get_active_skills())}\n"

        if self.skill_manager.get_active_skills():
            summary += "Active: " + ", ".join(self.skill_manager.get_active_skills().keys())

        return summary

    def get_current_model(self) -> str:
        """Get current model name.

        Returns:
            Current model name
        """
        return self.llm.model

    def set_model(self, model: str) -> str:
        """Set the model to use.

        Args:
            model: Model name

        Returns:
            Status message
        """
        old_model = self.llm.model
        self.llm.model = model
        self.llm.logger.info(f"Model changed from {old_model} to {model}")
        return f"Model changed from {old_model} to {model}"

    def list_available_models(self) -> List[str]:
        """List commonly available models.

        Returns:
            List of model names
        """
        return [
            # Claude models
            "claude-opus-4",
            "claude-sonnet-4-5",
            "claude-sonnet-4",
            "claude-haiku-4",
            # OpenAI models
            "gpt-4-turbo-preview",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4-32k",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            # Other common models
            "deepseek-chat",
            "deepseek-coder",
        ]
