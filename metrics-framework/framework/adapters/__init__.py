from __future__ import annotations

from .base import Adapter
from .csv_adapter import CSVAdapter
from .github_adapter import GitHubAdapter
from .jira_adapter import JiraAdapter
from .sql_adapter import SQLAdapter

ADAPTER_REGISTRY = {
    CSVAdapter.type_key: CSVAdapter,
    GitHubAdapter.type_key: GitHubAdapter,
    JiraAdapter.type_key: JiraAdapter,
    SQLAdapter.type_key: SQLAdapter,
}


def build_adapter(source_config) -> Adapter:
    """source_config: a framework.config.SourceConfig"""
    cls = ADAPTER_REGISTRY.get(source_config.type)
    if cls is None:
        raise ValueError(
            f"Source '{source_config.name}' has unknown type '{source_config.type}'. "
            f"Known adapter types: {sorted(ADAPTER_REGISTRY)}. "
            f"To add a new source system, write an Adapter subclass and register it here."
        )
    return cls(source_config.name, source_config.entity, source_config.options)
