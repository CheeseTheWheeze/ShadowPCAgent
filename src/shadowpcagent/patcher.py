from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from shadowpcagent.models import PatchResult


@dataclass
class Hunk:
    original_start: int
    original_count: int
    new_start: int
    new_count: int
    lines: List[str]


class UnifiedDiffApplier:
    def apply(self, diff_text: str, repo_root: Path) -> PatchResult:
        target_path = self._extract_target_path(diff_text)
        if target_path is None:
            return PatchResult(path="", applied=False, error="No target path found in diff.")
        path = (repo_root / target_path).resolve()
        if not path.exists():
            return PatchResult(
                path=str(path),
                applied=False,
                error="Target file does not exist.",
            )
        hunks = self._parse_hunks(diff_text)
        if not hunks:
            return PatchResult(path=str(path), applied=False, error="No hunks found.")
        original_lines = path.read_text(encoding="utf-8").splitlines()
        try:
            updated_lines = self._apply_hunks(original_lines, hunks)
        except ValueError as exc:
            return PatchResult(path=str(path), applied=False, error=str(exc))
        path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        return PatchResult(path=str(path), applied=True)

    def _extract_target_path(self, diff_text: str) -> Optional[str]:
        for line in diff_text.splitlines():
            if line.startswith("+++ "):
                target = line.replace("+++ ", "", 1).strip()
                return target
        return None

    def _parse_hunks(self, diff_text: str) -> List[Hunk]:
        hunks: List[Hunk] = []
        lines = diff_text.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.startswith("@@"):
                header = line.strip("@ ").split(" ")
                original_info = header[0].lstrip("-")
                new_info = header[1].lstrip("+")
                original_start, original_count = self._parse_range(original_info)
                new_start, new_count = self._parse_range(new_info)
                index += 1
                hunk_lines: List[str] = []
                while index < len(lines) and not lines[index].startswith("@@"):
                    hunk_lines.append(lines[index])
                    index += 1
                hunks.append(
                    Hunk(
                        original_start=original_start,
                        original_count=original_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=hunk_lines,
                    )
                )
            else:
                index += 1
        return hunks

    def _parse_range(self, value: str) -> tuple[int, int]:
        if "," in value:
            start, count = value.split(",", 1)
            return int(start), int(count)
        return int(value), 1

    def _apply_hunks(self, original_lines: List[str], hunks: List[Hunk]) -> List[str]:
        updated = original_lines[:]
        offset = 0
        for hunk in hunks:
            start_index = hunk.original_start - 1 + offset
            original_index = start_index
            new_chunk: List[str] = []
            for line in hunk.lines:
                if line.startswith(" "):
                    expected = line[1:]
                    if original_index >= len(updated) or updated[original_index] != expected:
                        raise ValueError("Context mismatch while applying patch.")
                    new_chunk.append(expected)
                    original_index += 1
                elif line.startswith("-"):
                    expected = line[1:]
                    if original_index >= len(updated) or updated[original_index] != expected:
                        raise ValueError("Deletion mismatch while applying patch.")
                    original_index += 1
                elif line.startswith("+"):
                    new_chunk.append(line[1:])
            updated[start_index:original_index] = new_chunk
            offset += len(new_chunk) - (original_index - start_index)
        return updated
