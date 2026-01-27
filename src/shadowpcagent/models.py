from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

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
class PatchResult:
    path: str
    applied: bool
    error: Optional[str] = None
    dry_run: bool = False
    validated: bool = False


@dataclass
class RunHistoryEntry:
    timestamp: str
    task: str
    status: str
    summary_path: Optional[str] = None


@dataclass
class RunSummary:
    status: str
    task: str
    plan: Plan
    actions: List[ActionLog]
    safety_report: "SafetyReport"
    files_scanned: int
    file_types: Dict[str, int]
    repo_root: str
    plan_only: bool
    shell_result: Optional[ShellResult] = None
    log_path: Optional[str] = None
    draft_path: Optional[str] = None
    edit_path: Optional[str] = None
    edit_diff: Optional[str] = None
    applied_patch: Optional[PatchResult] = None
    applied_patch_path: Optional[str] = None
    run_summary_path: Optional[str] = None
    run_history_path: Optional[str] = None
