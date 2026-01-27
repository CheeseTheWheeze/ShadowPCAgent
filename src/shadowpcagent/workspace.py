from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class WorkspaceScan:
    root: Path
    files: List[Path]
    file_types: Dict[str, int]

    @property
    def file_count(self) -> int:
        return len(self.files)


class WorkspaceScanner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def scan(self, max_files: int = 200) -> WorkspaceScan:
        files: List[Path] = []
        file_types: Dict[str, int] = {}
        for path in self.root.rglob("*"):
            if path.is_file():
                files.append(path)
                suffix = path.suffix.lower() or "<none>"
                file_types[suffix] = file_types.get(suffix, 0) + 1
            if len(files) >= max_files:
                break
        return WorkspaceScan(root=self.root, files=files, file_types=file_types)
