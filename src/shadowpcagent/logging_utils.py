import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


class JsonlLogger:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        self.path = self.log_dir / f"run-{timestamp}.jsonl"

    def log(self, event: str, payload: dict[str, Any]) -> None:
        record = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def log_dataclass(self, event: str, payload: Any) -> None:
        self.log(event, asdict(payload))


class RunHistoryLogger:
    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, payload: dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **payload,
        }
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
