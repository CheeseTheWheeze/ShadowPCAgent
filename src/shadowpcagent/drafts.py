from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DraftResult:
    path: Path
    diff: str


class DraftManager:
    def __init__(self, draft_dir: Path) -> None:
        self.draft_dir = draft_dir
        self.draft_dir.mkdir(parents=True, exist_ok=True)

    def write_note(self, note: str) -> DraftResult:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = self.draft_dir / f"draft-note-{timestamp}.patch"
        diff = "\n".join(
            [
                "--- draft/note.txt",
                "+++ draft/note.txt",
                "@@ -0,0 +1,2 @@",
                f"+Note: {note}",
                "+Status: Draft only (not applied).",
            ]
        )
        path.write_text(diff, encoding="utf-8")
        return DraftResult(path=path, diff=diff)

    def write_diff(self, diff: str) -> DraftResult:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = self.draft_dir / f"draft-change-{timestamp}.patch"
        path.write_text(diff, encoding="utf-8")
        return DraftResult(path=path, diff=diff)
