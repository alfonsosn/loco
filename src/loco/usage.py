"""Token usage and cost tracking for loco."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# Approximate cost per 1M tokens (as of 2024)
# Format: {model_prefix: (input_cost, output_cost)}
MODEL_COSTS = {
    # OpenAI GPT-4
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    
    # Anthropic Claude
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    
    # Other providers (approximate)
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "command-r-plus": (3.00, 15.00),
    "command-r": (0.50, 1.50),
}


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
