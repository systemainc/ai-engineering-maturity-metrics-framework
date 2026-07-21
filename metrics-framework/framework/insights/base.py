"""
InsightProvider interface — mirrors the adapter pattern in
framework/adapters/base.py: one small contract every backend implements,
so swapping providers never touches anything else.

Providers are deliberately dumb: they take a finished prompt string and
return finished text. All of the "what should this prompt say" logic lives
in framework/insights/prompt.py, and all of the "what facts is the model
even allowed to see" logic lives in framework/metrics/gap_analysis.py.
Keeping those separate means swapping providers can never accidentally
change what the model is told or what it's allowed to know.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class InsightProvider(ABC):
    #: provider type key, matched against `provider:` in the config's insights block
    type_key: str = "base"

    def __init__(self, options: dict):
        self.options = options

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the model's response text for this prompt.

        Raises on failure (bad auth, network error, non-2xx response) rather than
        swallowing it — the caller (framework/pipeline.py) is responsible for catching
        per-scope and degrading gracefully, the same convention already used for a
        broken data source.
        """
        raise NotImplementedError
