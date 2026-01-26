from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class WorkspaceScan:
    root: Path
    files: List[Path]

    @property
    def file_count(self) -> int:
        return len(self.files)


class WorkspaceScanner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def scan(self, max_files: int = 200) -> WorkspaceScan:
        files: List[Path] = []
        for path in self.root.rglob("*"):
            if path.is_file():
                files.append(path)
            if len(files) >= max_files:
                break
        return WorkspaceScan(root=self.root, files=files)
