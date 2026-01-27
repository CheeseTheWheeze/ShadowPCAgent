import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class AgentConfig:
    allowlist: set[str]
    max_files: int
    log_dir: Path
    draft_dir: Path


DEFAULT_CONFIG = AgentConfig(
    allowlist={"git", "ls", "pwd"},
    max_files=200,
    log_dir=Path(".shadowpcagent/logs"),
    draft_dir=Path(".shadowpcagent/drafts"),
)


def load_config(path: Path | None) -> AgentConfig:
    if path is None or not path.exists():
        return DEFAULT_CONFIG
    data = json.loads(path.read_text(encoding="utf-8"))
    allowlist = set(data.get("allowlist", DEFAULT_CONFIG.allowlist))
    max_files = int(data.get("max_files", DEFAULT_CONFIG.max_files))
    log_dir = Path(data.get("log_dir", str(DEFAULT_CONFIG.log_dir)))
    draft_dir = Path(data.get("draft_dir", str(DEFAULT_CONFIG.draft_dir)))
    return AgentConfig(
        allowlist=allowlist,
        max_files=max_files,
        log_dir=log_dir,
        draft_dir=draft_dir,
    )


def merge_allowlist(config: AgentConfig, allowlist: Iterable[str]) -> AgentConfig:
    merged = set(config.allowlist)
    merged.update(allowlist)
    return AgentConfig(
        allowlist=merged,
        max_files=config.max_files,
        log_dir=config.log_dir,
        draft_dir=config.draft_dir,
    )
