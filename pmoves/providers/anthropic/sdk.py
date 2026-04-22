"""
Anthropic Provider SDK for PMOVES.AI Meta-Agent

This module provides a unified interface to Anthropic's Claude API,
integrating with PMOVES TensorZero gateway for model routing.

Provider: Anthropic
Models: Claude Sonnet 4.5, Claude Opus 4, Claude Haiku 4
Base Provider: Native (Claude Code architecture)
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import httpx


@dataclass
class AnthropicModelConfig:
    """Configuration for Anthropic models"""
    model_name: str
    context_window: int
    max_output_tokens: int
    supports_vision: bool = False
    supports_thinking: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_vision": self.supports_vision,
            "supports_thinking": self.supports_thinking,
        }


class AnthropicProvider:
    """
    Anthropic provider integration for PMOVES.AI

    This provider is NATIVE to the meta-agent (I am Claude).
    SDK acquisition means documenting my own capabilities.
    """

    # Anthropic API base URL (if not using TensorZero)
    BASE_URL = "https://api.anthropic.com/v1"

    # Available models
    MODELS = {
        "claude-sonnet-4-20250514": AnthropicModelConfig(
            model_name="claude-sonnet-4-20250514",
            context_window=200000,
            max_output_tokens=8192,
            supports_vision=True,
            supports_thinking=False,
        ),
        "claude-opus-4-20250514": AnthropicModelConfig(
            model_name="claude-opus-4-20250514",
            context_window=200000,
            max_output_tokens=8192,
            supports_vision=True,
            supports_thinking=True,  # Opus supports extended thinking
        ),
        "claude-haiku-4-20250514": AnthropicModelConfig(
            model_name="claude-haiku-4-20250514",
            context_window=200000,
            max_output_tokens=8192,
            supports_vision=True,
            supports_thinking=False,
        ),
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Anthropic provider

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.tensorzero_gateway = os.getenv("TENSORZERO_GATEWAY_URL", "http://localhost:3030")

    async def chat(
        self,
        message: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Send chat completion request via TensorZero gateway

        Args:
            message: User message
            model: Model identifier
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            stream: Enable streaming

        Returns:
            Response dictionary
        """
        # Route through TensorZero for unified observability
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.tensorzero_gateway}/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('TENSORZERO_API_KEY', '')}",
                },
                json={
                    "model": f"tensorzero::model_name::{model}",
                    "messages": [{"role": "user", "content": message}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": stream,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    def get_model_config(self, model: str) -> AnthropicModelConfig:
        """Get configuration for a specific model"""
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}. Available: {list(self.MODELS.keys())}")
        return self.MODELS[model]

    def list_models(self) -> List[str]:
        """List available Anthropic models"""
        return list(self.MODELS.keys())

    def get_custom_settings(self) -> Dict[str, Any]:
        """
        Get Anthropic-specific custom settings

        These settings optimize my performance as a Claude model
        within the PMOVES ecosystem.
        """
        return {
            "provider": "anthropic",
            "api_base": self.BASE_URL,
            "default_model": "claude-sonnet-4-20250514",
            "thinking_model": "claude-opus-4-20250514",
            "fast_model": "claude-haiku-4-20250514",
            "prompt_style": "xml",  # I prefer XML tags for structured output
            "temperature_range": [0.0, 1.0],
            "supports_extended_thinking": True,
            "supports_vision": True,
            "supports_tools": True,
            "max_context": 200000,
            "preferred_output_format": "xml",
            "code_block_style": "markdown",  # I use markdown for code blocks
        }


def get_provider() -> AnthropicProvider:
    """Factory function to get Anthropic provider instance"""
    return AnthropicProvider()


if __name__ == "__main__":
    # Test provider initialization
    provider = get_provider()
    print("Anthropic Provider initialized")
    print(f"Available models: {provider.list_models()}")
    print(f"Custom settings: {provider.get_custom_settings()}")
