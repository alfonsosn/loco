"""Configuration management for loco."""

import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Configuration for a specific provider."""

    api_key: str | None = None
    api_base: str | None = None
    aws_region: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ToolsConfig(BaseModel):
    """Configuration for tools."""

    bash_enabled: bool = True
    bash_timeout: int = 120
    require_confirmation: bool = False


class MCPServerConfig(BaseModel):
    """Configuration for an external MCP server.
    
    Supports two types:
    - command: Local process-based MCP server (default)
    - http: HTTP-based MCP server with optional headers
    """

    # Type discriminator
    type: str = Field(default="command", pattern="^(command|http)$")
    
    # Command-based config (type="command")
    command: list[str] | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    
    # HTTP-based config (type="http")
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    
    def model_post_init(self, __context: Any) -> None:
        """Validate config based on type."""
        if self.type == "command":
            if not self.command:
                raise ValueError("Command-based MCP server must have 'command' field")
        elif self.type == "http":
            if not self.url:
                raise ValueError("HTTP-based MCP server must have 'url' field")


class Config(BaseModel):
    """Main configuration for loco."""

    default_model: str = "openai/gpt-4o"
    models: dict[str, str] = Field(default_factory=lambda: {
        "gpt4": "openai/gpt-4o",
        "gpt4-mini": "openai/gpt-4o-mini",
        "sonnet": "bedrock/us.anthropic.claude-sonnet-4-20250514",
        "local": "ollama/llama3",
    })
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    hooks: dict[str, Any] = Field(default_factory=dict)
    mcp_servers: dict[str, dict[str, Any] | MCPServerConfig] = Field(default_factory=dict)
    system_prompt: str | None = None


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(config_home) / "loco"


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


def expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in config values.

    Supports ${VAR} and $VAR syntax.
    """
    if isinstance(value, str):
        # Match ${VAR} or $VAR patterns
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'

        def replace(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))

        return re.sub(pattern, replace, value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


def load_config() -> Config:
    """Load configuration from file, creating default if it doesn't exist."""
    config_path = get_config_path()

    if not config_path.exists():
        # Create default config
        config = Config()
        save_config(config)
        return config

    # Check file permissions and warn if too permissive
    file_stat = config_path.stat()
    if file_stat.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        from rich.console import Console
        console = Console(stderr=True)
        console.print(
            "[yellow]Warning:[/yellow] Config file has overly permissive permissions. "
            f"Consider running: chmod 600 {config_path}"
        )

    with open(config_path) as f:
        data = json.load(f)

    # Expand environment variables
    data = expand_env_vars(data)

    return Config.model_validate(data)


def save_config(config: Config) -> None:
    """Save configuration to file."""
    config_dir = get_config_dir()
    config_path = get_config_path()

    # Create directory with secure permissions
    config_dir.mkdir(parents=True, exist_ok=True)

    # Write config with restricted permissions
    with open(config_path, "w") as f:
        json.dump(config.model_dump(exclude_none=True), f, indent=2)

    # Set file permissions to user-only read/write
    os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)


def resolve_model(model: str, config: Config) -> str:
    """Resolve a model alias to its full model string.

    If the model is an alias defined in config.models, return the full model string.
    Otherwise, return the model as-is (assumed to be a full LiteLLM model string).
    """
    return config.models.get(model, model)


def get_provider_config(model: str, config: Config) -> dict[str, Any]:
    """Get provider-specific configuration for a model.

    Extracts the provider from the model string (e.g., 'openai' from 'openai/gpt-4o')
    and returns any provider-specific settings.
    """
    # Extract provider from model string
    if "/" in model:
        provider = model.split("/")[0]
    else:
        provider = "openai"  # Default provider

    provider_config = config.providers.get(provider, ProviderConfig())

    result: dict[str, Any] = {}

    if provider_config.api_key:
        result["api_key"] = provider_config.api_key
    if provider_config.api_base:
        result["api_base"] = provider_config.api_base
    if provider_config.aws_region:
        result["aws_region_name"] = provider_config.aws_region

    result.update(provider_config.extra)

    return result
