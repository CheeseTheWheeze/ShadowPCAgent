from pathlib import Path

from shadowpcagent.drafts import DraftManager
from shadowpcagent.editor import EditRequest, FileEditor
from shadowpcagent.executors import ShellExecutor
from shadowpcagent.gui import GuiExecutor
from shadowpcagent.logging_utils import JsonlLogger
from shadowpcagent.models import ActionLog, Plan, PlanStep, RunSummary
from shadowpcagent.safety import SafetyEngine
from shadowpcagent.workspace import WorkspaceScanner


class Planner:
    def build_plan(self, task: str) -> Plan:
        steps = [
            PlanStep(title="Analyze task", description=f"Understand: {task}"),
            PlanStep(title="Prepare", description="Gather context and resources"),
            PlanStep(title="Execute", description="Run executors for code/GUI work"),
            PlanStep(title="Report", description="Summarize results and logs"),
        ]
        return Plan(task=task, steps=steps)


class Orchestrator:
    def __init__(self, allowlist: set[str], log_dir: Path, draft_dir: Path) -> None:
        self.planner = Planner()
        self.gui_executor = GuiExecutor()
        self.safety_engine = SafetyEngine()
        self.shell_executor = ShellExecutor(allowlist=allowlist)
        self.logger = JsonlLogger(log_dir=log_dir)
        self.draft_manager = DraftManager(draft_dir=draft_dir)
        self.editor = FileEditor()

    def run(
        self,
        task: str,
        approve_sensitive: bool,
        repo_root: Path,
        command: str,
        draft_note: str | None,
        edit_request: EditRequest | None,
        max_files: int,
        plan_only: bool,
    ) -> RunSummary:
        plan = self.planner.build_plan(task)
        report = self.safety_engine.classify(task=task, plan=plan)
        actions: list[ActionLog] = []
        scan = WorkspaceScanner(repo_root).scan(max_files=max_files)
        self.logger.log("plan_built", {"task": task, "steps": [s.title for s in plan.steps]})
        self.logger.log(
            "workspace_scan",
            {
                "files": scan.file_count,
                "root": str(repo_root),
                "file_types": scan.file_types,
            },
        )
        actions.append(
            ActionLog(
                action="Scan workspace",
                succeeded=True,
                detail=f"Scanned {scan.file_count} files under {repo_root}",
            )
        )
        draft_path = None
        edit_diff = None
        edit_path = None
        if draft_note:
            draft = self.draft_manager.write_note(draft_note)
            draft_path = str(draft.path)
            self.logger.log("draft_created", {"path": draft_path})
            actions.append(
                ActionLog(
                    action="Create draft note",
                    succeeded=True,
                    detail=f"Draft written to {draft_path}",
                )
            )
        if edit_request:
            edit_path = str(edit_request.path)
            if self.safety_engine.is_sensitive_path(edit_path) and not approve_sensitive:
                report.requires_approval = True
                report.reasons.append(f"Sensitive path detected: {edit_path}")
            edit_result = self.editor.apply_edit(edit_request)
            edit_diff = edit_result.diff
            self.logger.log(
                "edit_attempt",
                {
                    "path": edit_path,
                    "changed": edit_result.changed,
                    "applied": edit_result.applied,
                    "error": edit_result.error,
                },
            )
            if edit_result.diff:
                draft = self.draft_manager.write_diff(edit_result.diff)
                draft_path = draft_path or str(draft.path)
                self.logger.log("draft_created", {"path": draft_path})
            actions.append(
                ActionLog(
                    action="Edit file",
                    succeeded=edit_result.error is None,
                    detail=edit_result.error
                    or f"Edit {'applied' if edit_result.applied else 'drafted'} for {edit_path}",
                )
            )
        if report.requires_approval and not approve_sensitive:
            summary = RunSummary(
                status="approval_required",
                task=task,
                plan=plan,
                actions=actions,
                safety_report=report,
                files_scanned=scan.file_count,
                file_types=scan.file_types,
                repo_root=str(repo_root),
                plan_only=False,
                log_path=str(self.logger.path),
                draft_path=draft_path,
                edit_path=edit_path,
                edit_diff=edit_diff,
            )
            self.logger.log_dataclass("run_summary", summary)
            return summary

        if plan_only:
            summary = RunSummary(
                status="planned",
                task=task,
                plan=plan,
                actions=actions,
                safety_report=report,
                files_scanned=scan.file_count,
                file_types=scan.file_types,
                repo_root=str(repo_root),
                plan_only=True,
                log_path=str(self.logger.path),
                draft_path=draft_path,
                edit_path=edit_path,
                edit_diff=edit_diff,
            )
            self.logger.log_dataclass("run_summary", summary)
            return summary

        gui_result = self.gui_executor.perform_action("Open application")
        actions.append(
            ActionLog(
                action=gui_result.action,
                succeeded=gui_result.succeeded,
                detail=f"GUI action at {gui_result.timestamp}",
            )
        )

        shell_result = self.shell_executor.run(command)
        self.logger.log("shell_command", shell_result.__dict__)
        actions.append(
            ActionLog(
                action="Run command",
                succeeded=shell_result.returncode == 0,
                detail=f"Command '{command}' exited {shell_result.returncode}",
            )
        )

        self.gui_executor.perform_action("Execute task steps")
        summary = RunSummary(
            status="completed",
            task=task,
            plan=plan,
            actions=actions,
            safety_report=report,
            files_scanned=scan.file_count,
            file_types=scan.file_types,
            repo_root=str(repo_root),
            plan_only=False,
            shell_result=shell_result,
            log_path=str(self.logger.path),
            draft_path=draft_path,
            edit_path=edit_path,
            edit_diff=edit_diff,
        )
        self.logger.log_dataclass("run_summary", summary)
        return summary
