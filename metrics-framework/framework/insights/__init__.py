"""
Registry of insight providers, mirroring framework/adapters/__init__.py's
ADAPTER_REGISTRY. Adding a new LLM backend means writing one class with a
`generate(prompt) -> str` method (see base.py) and adding it here — nothing
else in the pipeline changes.
"""
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider

PROVIDER_REGISTRY = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


def build_provider(provider_type: str, options: dict):
    cls = PROVIDER_REGISTRY.get(provider_type)
    if cls is None:
        raise ValueError(f"Unknown insights provider '{provider_type}'. Known: {sorted(PROVIDER_REGISTRY)}")
    return cls(options)
