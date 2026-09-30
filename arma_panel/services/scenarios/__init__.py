"""Scenario catalogue: vanilla scenarios plus the ones found in installed addons."""

from .discovery import all_scenarios, all_scenarios_cached, count_by_source, get_map_name

__all__ = ["all_scenarios", "all_scenarios_cached", "count_by_source", "get_map_name"]
