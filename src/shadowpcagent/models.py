from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from shadowpcagent.safety import SafetyReport


@dataclass
class PlanStep:
    title: str
    description: str


@dataclass
class Plan:
    task: str
    steps: List[PlanStep] = field(default_factory=list)


@dataclass
class ActionLog:
    action: str
    succeeded: bool
    detail: str


@dataclass
class ShellResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


@dataclass
class RunSummary:
    status: str
    task: str
    plan: Plan
    actions: List[ActionLog]
    safety_report: "SafetyReport"
    files_scanned: int
    repo_root: str
    shell_result: Optional[ShellResult] = None
