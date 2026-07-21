"""
OpenAIProvider — calls the Chat Completions API directly over HTTPS. Same
"no extra SDK dependency" convention as AnthropicProvider; see that file's
docstring for why.

Config options (under `insights:` in config.yaml, when provider: openai):
    model:        required, e.g. "gpt-4o-mini"
    api_key_env:  required, name of the env var holding the API key
    max_tokens:   optional, default 200
"""
from __future__ import annotations

import os

import requests

from .base import InsightProvider

API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(InsightProvider):
    type_key = "openai"

    def __init__(self, options: dict):
        super().__init__(options)
        for required in ("model", "api_key_env"):
            if required not in options:
                raise ValueError(f"insights provider 'openai' is missing required option '{required}'")
        api_key = os.environ.get(options["api_key_env"])
        if not api_key:
            raise ValueError(
                f"insights provider 'openai': environment variable "
                f"{options['api_key_env']} is not set"
            )
        self.model = options["model"]
        self.max_tokens = options.get("max_tokens", 200)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def generate(self, prompt: str) -> str:
        resp = self.session.post(API_URL, json={
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        choices = body.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message", {}).get("content") or "").strip()
