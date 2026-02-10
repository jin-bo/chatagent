"""ChatAgent - A CLI chat agent with tools and skills support."""

__version__ = "0.1.0"

from .agent import ChatAgent
from .skills import SkillManager

__all__ = ["ChatAgent", "SkillManager"]
