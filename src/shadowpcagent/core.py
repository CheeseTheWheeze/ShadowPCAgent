from pathlib import Path

from shadowpcagent.executors import ShellExecutor
from shadowpcagent.gui import GuiExecutor
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
    def __init__(self) -> None:
        self.planner = Planner()
        self.gui_executor = GuiExecutor()
        self.safety_engine = SafetyEngine()
        self.shell_executor = ShellExecutor(allowlist={"git", "ls", "pwd"})

    def run(
        self,
        task: str,
        approve_sensitive: bool,
        repo_root: Path,
        command: str,
    ) -> RunSummary:
        plan = self.planner.build_plan(task)
        report = self.safety_engine.classify(task=task, plan=plan)
        actions: list[ActionLog] = []
        scan = WorkspaceScanner(repo_root).scan()
        actions.append(
            ActionLog(
                action="Scan workspace",
                succeeded=True,
                detail=f"Scanned {scan.file_count} files under {repo_root}",
            )
        )
        if report.requires_approval and not approve_sensitive:
            return RunSummary(
                status="approval_required",
                task=task,
                plan=plan,
                actions=actions,
                safety_report=report,
                files_scanned=scan.file_count,
                repo_root=str(repo_root),
            )

        gui_result = self.gui_executor.perform_action("Open application")
        actions.append(
            ActionLog(
                action=gui_result.action,
                succeeded=gui_result.succeeded,
                detail=f"GUI action at {gui_result.timestamp}",
            )
        )

        shell_result = self.shell_executor.run(command)
        actions.append(
            ActionLog(
                action="Run command",
                succeeded=shell_result.returncode == 0,
                detail=f"Command '{command}' exited {shell_result.returncode}",
            )
        )

        self.gui_executor.perform_action("Execute task steps")
        return RunSummary(
            status="completed",
            task=task,
            plan=plan,
            actions=actions,
            safety_report=report,
            files_scanned=scan.file_count,
            repo_root=str(repo_root),
            shell_result=shell_result,
        )
