"""
Z.AI Provider SDK for PMOVES.AI Meta-Agent

This module provides a unified interface to Z.AI's GLM Coding Plan API,
integrating with PMOVES TensorZero gateway for model routing.

Provider: Z.AI (Zhipu AI)
Documentation: https://docs.z.ai/devpack/overview
Models: GLM-4.7 (primary), GLM-5, GLM-5-Turbo, GLM-4.5-Air, GLM-5.1
Base Provider: Runtime (meta-agent uses GLM Coding Plan)
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import httpx


@dataclass
class GLMModelConfig:
    """Configuration for Z.AI GLM models"""
    model_name: str
    context_window: int
    max_output_tokens: int
    supports_vision: bool = False
    supports_function_call: bool = False
    supports_thinking: bool = False  # GLM-5 Turbo, GLM-5.1 support thinking parameter
    supports_openclaw: bool = False  # GLM-5 Turbo optimized for OpenClaw scenario
    api_endpoint: str = "https://api.z.ai/api/paas/v4"  # Default endpoint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_vision": self.supports_vision,
            "supports_function_call": self.supports_function_call,
            "supports_thinking": self.supports_thinking,
            "supports_openclaw": self.supports_openclaw,
            "api_endpoint": self.api_endpoint,
        }


class ZAIProvider:
    """
    Z.AI provider integration for PMOVES.AI

    This is the NATIVE RUNTIME provider for the meta-agent.
    I am powered by GLM-5.1 through this provider.
    """

    # Z.AI GLM Coding Plan API base URL (if not using TensorZero)
    # Official endpoint: https://api.z.ai/api/coding/paas/v4
    BASE_URL = "https://api.z.ai/api/coding/paas/v4"

    # Available models from Z.AI GLM Coding Plan
    MODELS = {
        "glm-5-turbo": GLMModelConfig(
            model_name="glm-5-turbo",
            context_window=128000,
            max_output_tokens=8192,
            supports_vision=True,
            supports_function_call=True,
            supports_thinking=True,  # GLM-5 Turbo supports thinking parameter
            supports_openclaw=True,  # Optimized for OpenClaw scenario
            api_endpoint="https://api.z.ai/api/paas/v4",  # GLM-5 Turbo endpoint
        ),
        "glm-5.1": GLMModelConfig(
            model_name="glm-5.1",
            context_window=128000,
            max_output_tokens=8192,
            supports_vision=True,
            supports_function_call=True,
            supports_thinking=True,  # GLM-5.1 supports thinking parameter
            supports_openclaw=False,
            api_endpoint="https://api.z.ai/api/coding/paas/v4",  # GLM Coding Plan endpoint
        ),
        "glm-5": GLMModelConfig(
            model_name="glm-5",
            context_window=128000,
            max_output_tokens=8192,
            supports_vision=True,
            supports_function_call=True,
            supports_thinking=True,
            supports_openclaw=False,
            api_endpoint="https://api.z.ai/api/coding/paas/v4",
        ),
        "glm-4.7": GLMModelConfig(
            model_name="glm-4.7",
            context_window=128000,
            max_output_tokens=8192,
            supports_vision=True,
            supports_function_call=True,
            supports_thinking=False,
            supports_openclaw=False,
            api_endpoint="https://api.z.ai/api/coding/paas/v4",
        ),
        "glm-4.5-air": GLMModelConfig(
            model_name="glm-4.5-air",
            context_window=128000,
            max_output_tokens=4096,
            supports_vision=False,
            supports_function_call=True,
            supports_thinking=False,
            supports_openclaw=False,
            api_endpoint="https://api.z.ai/api/coding/paas/v4",
        ),
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Z.AI provider

        Args:
            api_key: Z.AI API key (defaults to Z_AI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("Z_AI_API_KEY")
        self.tensorzero_gateway = os.getenv("TENSORZERO_GATEWAY_URL", "http://localhost:3030")

    async def chat(
        self,
        message: str,
        model: str = "glm-5-turbo",  # Primary fast model
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
        thinking: bool = None,  # Enable thinking parameter for GLM-5 Turbo/5.1
    ) -> Dict[str, Any]:
        """
        Send chat completion request via TensorZero gateway

        Args:
            message: User message
            model: Model identifier
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            stream: Enable streaming
            thinking: Enable thinking parameter (GLM-5 Turbo, GLM-5.1)

        Returns:
            Response dictionary
        """
        # Get model config to check if thinking is supported
        model_config = self.get_model_config(model)

        # Auto-enable thinking for models that support it if not explicitly set
        enable_thinking = thinking
        if enable_thinking is None and model_config.supports_thinking:
            enable_thinking = True

        # Build request body
        request_body = {
            "model": f"tensorzero::model_name::{model}",
            "messages": [{"role": "user", "content": message}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        # Add thinking parameter if supported
        if enable_thinking and model_config.supports_thinking:
            request_body["thinking"] = {"type": "enabled"}

        # Route through TensorZero for unified observability
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.tensorzero_gateway}/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('TENSORZERO_API_KEY', '')}",
                },
                json=request_body,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    def get_model_config(self, model: str) -> GLMModelConfig:
        """Get configuration for a specific model"""
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}. Available: {list(self.MODELS.keys())}")
        return self.MODELS[model]

    def list_models(self) -> List[str]:
        """List available Z.AI models"""
        return list(self.MODELS.keys())

    async def chat_direct(
        self,
        message: str,
        model: str = "glm-5-turbo",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
        thinking: bool = None,
    ) -> Dict[str, Any]:
        """
        Send chat completion request directly to Z.AI API (bypassing TensorZero)

        Uses model-specific API endpoints:
        - GLM-5 Turbo: https://api.z.ai/api/paas/v4/chat/completions
        - GLM Coding Plan models: https://api.z.ai/api/coding/paas/v4

        Args:
            message: User message
            model: Model identifier
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            stream: Enable streaming
            thinking: Enable thinking parameter (GLM-5 Turbo, GLM-5.1)

        Returns:
            Response dictionary
        """
        # Get model config to check capabilities and endpoint
        model_config = self.get_model_config(model)

        # Auto-enable thinking for models that support it if not explicitly set
        enable_thinking = thinking
        if enable_thinking is None and model_config.supports_thinking:
            enable_thinking = True

        # Build request body following official Z.AI SDK pattern
        request_body = {
            "model": model_config.model_name,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        # Add thinking parameter if supported (official GLM-5 Turbo feature)
        if enable_thinking and model_config.supports_thinking:
            request_body["thinking"] = {"type": "enabled"}

        # Use model-specific API endpoint
        api_endpoint = model_config.api_endpoint

        # Direct API call (not through TensorZero)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_endpoint}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json=request_body,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    def get_custom_settings(self) -> Dict[str, Any]:
        """
        Get Z.AI-specific custom settings

        These settings optimize my performance as a GLM model
        within the PMOVES ecosystem.
        """
        return {
            "provider": "zai",
            "api_base": self.BASE_URL,
            "default_model": "glm-5-turbo",  # Primary fast model
            "fast_model": "glm-5-turbo",
            "standard_model": "glm-5.1",  # Standard for complex tasks
            "balanced_model": "glm-4.5-air",
            "premium_model": "glm-5",
            "prompt_style": "instruction",
            "temperature_range": [0.0, 1.0],
            "supports_function_calling": True,
            "supports_vision": True,  # GLM-5.1, GLM-5, GLM-5-Turbo
            "supports_thinking": True,  # GLM-5 Turbo, GLM-5.1
            "supports_openclaw": True,  # GLM-5 Turbo optimized for OpenClaw
            "max_context": 128000,
            "preferred_output_format": "json",
            "code_block_style": "markdown",
            "thinking_default": "enabled",  # Default for GLM-5 Turbo, GLM-5.1
            "api_endpoints": {
                "glm-5-turbo": "https://api.z.ai/api/paas/v4",
                "glm-coding-plan": "https://api.z.ai/api/coding/paas/v4",
            },
        }


def get_provider() -> ZAIProvider:
    """Factory function to get Z.AI provider instance"""
    return ZAIProvider()


if __name__ == "__main__":
    # Test provider initialization
    provider = get_provider()
    print("Z.AI Provider initialized")
    print(f"Available models: {provider.list_models()}")
    print(f"Custom settings: {provider.get_custom_settings()}")
