"""
AnthropicProvider — calls the Messages API directly over HTTPS. No `anthropic`
SDK dependency; same convention as framework/adapters/github_adapter.py
calling the GitHub REST API directly via `requests` rather than pulling in
PyGithub. One fewer dependency to version-pin, one fewer thing that can
break on an unrelated SDK upgrade.

Config options (under `insights:` in config.yaml, when provider: anthropic):
    model:        required, e.g. "claude-sonnet-4-5-20250929"
    api_key_env:  required, name of the env var holding the API key (never the key itself)
    max_tokens:   optional, default 200 — this is a 2-sentence note, not an essay
"""
from __future__ import annotations

import os

import requests

from .base import InsightProvider

API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(InsightProvider):
    type_key = "anthropic"

    def __init__(self, options: dict):
        super().__init__(options)
        for required in ("model", "api_key_env"):
            if required not in options:
                raise ValueError(f"insights provider 'anthropic' is missing required option '{required}'")
        api_key = os.environ.get(options["api_key_env"])
        if not api_key:
            raise ValueError(
                f"insights provider 'anthropic': environment variable "
                f"{options['api_key_env']} is not set"
            )
        self.model = options["model"]
        self.max_tokens = options.get("max_tokens", 200)
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })

    def generate(self, prompt: str) -> str:
        resp = self.session.post(API_URL, json={
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        parts = body.get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
