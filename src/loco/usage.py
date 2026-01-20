"""Token usage and cost tracking for loco."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# Model information: costs and context windows
# Format: {model_prefix: (input_cost, output_cost, context_window)}
# Costs are per 1M tokens, context window is total tokens
MODEL_INFO = {
    # OpenAI GPT-4
    "gpt-4o": (2.50, 10.00, 128_000),
    "gpt-4o-mini": (0.15, 0.60, 128_000),
    "gpt-4-turbo": (10.00, 30.00, 128_000),
    "gpt-4": (30.00, 60.00, 8_192),
    "gpt-3.5-turbo": (0.50, 1.50, 16_385),

    # Anthropic Claude
    "claude-3-5-sonnet": (3.00, 15.00, 200_000),
    "claude-3-opus": (15.00, 75.00, 200_000),
    "claude-3-sonnet": (3.00, 15.00, 200_000),
    "claude-3-haiku": (0.25, 1.25, 200_000),

    # Other providers (approximate)
    "gemini-1.5-pro": (1.25, 5.00, 2_000_000),
    "gemini-1.5-flash": (0.075, 0.30, 1_000_000),
    "command-r-plus": (3.00, 15.00, 128_000),
    "command-r": (0.50, 1.50, 128_000),
}

# Backward compatibility alias
MODEL_COSTS = {k: v[:2] for k, v in MODEL_INFO.items()}


def get_model_context_window(model: str) -> int | None:
    """Get the context window size for a model.

    Args:
        model: The model identifier

    Returns:
        Context window size in tokens, or None if unknown
    """
    for model_prefix, info in MODEL_INFO.items():
        if model_prefix in model.lower():
            return info[2]  # Third element is context window

    return None


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate the cost of a completion based on token usage.

    Args:
        model: The model identifier
        prompt_tokens: Number of input/prompt tokens
        completion_tokens: Number of output/completion tokens

    Returns:
        Estimated cost in USD
    """
    # Find matching cost entry
    input_cost, output_cost = None, None

    for model_prefix, costs in MODEL_COSTS.items():
        if model_prefix in model.lower():
            input_cost, output_cost = costs
            break

    # If no match found, use a conservative estimate
    if input_cost is None:
        input_cost, output_cost = 5.00, 15.00

    # Calculate cost (prices are per 1M tokens)
    total_cost = (prompt_tokens * input_cost / 1_000_000) + \
                 (completion_tokens * output_cost / 1_000_000)

    return total_cost


def estimate_conversation_tokens(conversation: Any) -> int:
    """Estimate total tokens in a conversation.

    This is a rough estimate based on message content length.
    For more accurate counts, you'd need model-specific tokenizers.

    Args:
        conversation: A Conversation object with messages

    Returns:
        Estimated token count
    """
    total_chars = 0

    for msg in conversation.messages:
        if msg.content:
            total_chars += len(msg.content)

        # Tool calls add overhead
        if msg.tool_calls:
            import json
            total_chars += len(json.dumps(msg.tool_calls))

    # Rough estimate: ~4 characters per token (conservative for English)
    # This varies by model and language
    estimated_tokens = total_chars // 4

    # Add overhead for message formatting, system prompts, etc.
    # Typical overhead is ~10-20 tokens per message
    message_overhead = len(conversation.messages) * 15

    return estimated_tokens + message_overhead


@dataclass
class UsageStats:
    """Statistics for a single API call."""
    
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def from_response(cls, model: str, usage_data: dict[str, Any]) -> "UsageStats":
        """Create UsageStats from LiteLLM response usage data.
        
        Args:
            model: The model identifier
            usage_data: The usage dict from response (with prompt_tokens, completion_tokens, etc.)
            
        Returns:
            UsageStats object
        """
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)
        
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        
        return cls(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageStats":
        """Create from dictionary."""
        return cls(
            model=data["model"],
            prompt_tokens=data["prompt_tokens"],
            completion_tokens=data["completion_tokens"],
            total_tokens=data["total_tokens"],
            cost=data["cost"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class SessionUsage:
    """Accumulated usage statistics for a session."""
    
    stats: list[UsageStats] = field(default_factory=list)
    
    def add(self, stat: UsageStats) -> None:
        """Add a usage stat to this session."""
        self.stats.append(stat)
    
    def get_total_tokens(self) -> int:
        """Get total tokens used in this session."""
        return sum(s.total_tokens for s in self.stats)
    
    def get_total_cost(self) -> float:
        """Get total estimated cost for this session."""
        return sum(s.cost for s in self.stats)
    
    def get_prompt_tokens(self) -> int:
        """Get total prompt tokens used."""
        return sum(s.prompt_tokens for s in self.stats)
    
    def get_completion_tokens(self) -> int:
        """Get total completion tokens used."""
        return sum(s.completion_tokens for s in self.stats)
    
    def get_call_count(self) -> int:
        """Get number of API calls made."""
        return len(self.stats)

    def get_context_percentage(self, model: str, estimated_conversation_tokens: int) -> float | None:
        """Get percentage of context window used.

        Args:
            model: The model identifier
            estimated_conversation_tokens: Estimated tokens in conversation

        Returns:
            Percentage (0-100) of context window used, or None if unknown
        """
        context_window = get_model_context_window(model)
        if context_window is None:
            return None

        if context_window == 0:
            return None

        return (estimated_conversation_tokens / context_window) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "stats": [s.to_dict() for s in self.stats],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionUsage":
        """Create from dictionary."""
        stats = [UsageStats.from_dict(s) for s in data.get("stats", [])]
        return cls(stats=stats)
