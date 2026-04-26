"""Adapter interfaces and implementations."""

from software_factory.core.adapters.codex import CodexAdapter
from software_factory.core.adapters.interface import AgentAdapter

__all__ = ["AgentAdapter", "CodexAdapter"]
