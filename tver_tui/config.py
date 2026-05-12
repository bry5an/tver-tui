from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".config" / "tver-dl" / "config.yaml"


@dataclass
class ConfigSeries:
    name: str
    url: str
    subtitles: bool


@dataclass
class ConfigGroup:
    name: str
    series: list[ConfigSeries] = field(default_factory=list)


def load_config(path: Path = CONFIG_PATH) -> list[ConfigGroup]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    series_map: dict = (data or {}).get("series") or {}
    groups: list[ConfigGroup] = []
    for group_name, items in series_map.items():
        if not items:
            continue
        group = ConfigGroup(name=group_name)
        for item in items:
            if not item.get("enabled", True):
                continue
            name = item.get("name", "")
            url = item.get("url", "")
            if not name or not url:
                continue
            group.series.append(
                ConfigSeries(name=name, url=url, subtitles=item.get("subtitles", True))
            )
        if group.series:
            groups.append(group)
    return groups
