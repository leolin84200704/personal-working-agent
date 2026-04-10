"""
Configuration Management - Centralized settings with Pydantic.

Loads settings from environment variables and .env file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Union, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_agent_root() -> Path:
    """Get the agent root directory (contains SOUL.md, IDENTITY.md, etc.)."""
    # Start from current file and go up
    current = Path(__file__).parent.parent
    if (current / "SOUL.md").exists():
        return current
    # Fallback to script directory
    return Path.cwd()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Agent Root
    agent_root: Path = Field(default_factory=get_agent_root)

    # Claude API
    anthropic_api_key: str
    anthropic_base_url: Optional[str] = None
    api_timeout_ms: int = 300000

    # Jira
    jira_server: str
    jira_email: str
    jira_api_token: str

    # Git
    git_user_name: str = "LIS Code Agent"
    git_user_email: str = "lis-code-agent@local"

    # Paths
    repos_base_path: Path = Field(default="/Users/hung.l/src")
    storage_path: Path = Field(default_factory=lambda: get_agent_root() / "storage")

    # Branch prefixes
    branch_prefix_feature: str = "feature/leo"
    branch_prefix_bugfix: str = "bugfix/leo"

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # Vector Store
    vector_store_path: Path = Field(default_factory=lambda: Path("./storage/chroma"))
    embedding_model: str = "all-MiniLM-L6-v2"  # sentence-transformers model

    # Agent Behavior
    max_conversation_history: int = 20
    max_retrieved_memories: int = 5
    auto_update_memory: bool = True

    # Flow / Webhook
    jira_webhook_secret: str = ""  # Optional: Jira webhook signature secret
    flow_post_to_jira: bool = False  # Post triage results as Jira comments
    poll_interval_minutes: int = 60  # Jira polling interval (0 = disabled)
    flow_timeout_seconds: int = 600  # Max time per flow execution (default 10 min)
    claude_allowed_tools: str = ""  # Claude CLI --allowedTools (e.g., "mcp__vibrant__*,Bash,Read,Edit")


    @field_validator("repos_base_path", "storage_path", "vector_store_path", "agent_root", mode="before")
    @classmethod
    def resolve_paths(cls, v: Union[str, Path]) -> Path:
        """Resolve string paths to Path objects, expanding ~."""
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v

    @property
    def soul_path(self) -> Path:
        return self.agent_root / "SOUL.md"

    @property
    def identity_path(self) -> Path:
        return self.agent_root / "IDENTITY.md"

    @property
    def user_path(self) -> Path:
        return self.agent_root / "USER.md"

    @property
    def memory_path(self) -> Path:
        return self.agent_root / "MEMORY.md"

    @property
    def conversations_path(self) -> Path:
        return self.storage_path / "conversations"

    @property
    def chroma_path(self) -> Path:
        return self.storage_path / "chroma"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance (lazy loaded)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
