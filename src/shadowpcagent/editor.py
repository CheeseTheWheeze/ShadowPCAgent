from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import difflib


@dataclass
class EditRequest:
    path: Path
    find_text: str
    replace_text: str
    apply: bool


@dataclass
class EditResult:
    path: Path
    diff: str
    applied: bool
    changed: bool
    error: Optional[str] = None


class FileEditor:
    def apply_edit(self, request: EditRequest) -> EditResult:
        if not request.path.exists():
            return EditResult(
                path=request.path,
                diff="",
                applied=False,
                changed=False,
                error="File not found.",
            )

        original = request.path.read_text(encoding="utf-8")
        updated = original.replace(request.find_text, request.replace_text)
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                updated.splitlines(),
                fromfile=str(request.path),
                tofile=str(request.path),
                lineterm="",
            )
        )

        changed = original != updated
        if request.apply and changed:
            request.path.write_text(updated, encoding="utf-8")
            return EditResult(
                path=request.path,
                diff=diff,
                applied=True,
                changed=True,
            )

        return EditResult(
            path=request.path,
            diff=diff,
            applied=False,
            changed=changed,
        )
