from dataclasses import dataclass
from subprocess import CompletedProcess, run
from typing import Iterable

from shadowpcagent.models import ShellResult


@dataclass
class Allowlist:
    commands: set[str]

    def allows(self, command: str) -> bool:
        base = command.strip().split()[0]
        return base in self.commands


class ShellExecutor:
    def __init__(self, allowlist: Iterable[str]) -> None:
        self.allowlist = Allowlist(commands=set(allowlist))

    def run(self, command: str) -> ShellResult:
        if not self.allowlist.allows(command):
            raise ValueError(f"Command not allowlisted: {command}")
        completed: CompletedProcess[str] = run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        return ShellResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
