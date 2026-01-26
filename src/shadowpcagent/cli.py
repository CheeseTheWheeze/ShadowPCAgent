import argparse
import json
from pathlib import Path
from typing import Sequence

from shadowpcagent.core import Orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ShadowPCAgent prototype runner",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default="Review repository and propose improvements",
        help="Task description for the agent to execute.",
    )
    parser.add_argument(
        "--approve-sensitive",
        action="store_true",
        help="Allow the prototype to proceed with sensitive tasks.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to scan for the demo run.",
    )
    parser.add_argument(
        "--command",
        default="git status -sb",
        help="Allowlisted shell command to execute as part of the run.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output a JSON summary.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    orchestrator = Orchestrator()
    summary = orchestrator.run(
        task=args.task,
        approve_sensitive=args.approve_sensitive,
        repo_root=Path(args.root),
        command=args.command,
    )

    if summary.status == "approval_required":
        if args.json:
            payload = {
                "status": "approval_required",
                "reasons": summary.safety_report.reasons,
                "draft_diff": summary.safety_report.draft_diff,
                "files_scanned": summary.files_scanned,
            }
            print(json.dumps(payload, indent=2))
        else:
            print("Sensitive changes detected. Approval required.")
            for reason in summary.safety_report.reasons:
                print(f"- {reason}")
            print("\nDraft diff:")
            print(summary.safety_report.draft_diff)
        return 2

    if args.json:
        payload = {
            "status": summary.status,
            "reasons": summary.safety_report.reasons,
            "files_scanned": summary.files_scanned,
            "repo_root": summary.repo_root,
            "shell": {
                "command": summary.shell_result.command,
                "returncode": summary.shell_result.returncode,
                "stdout": summary.shell_result.stdout,
                "stderr": summary.shell_result.stderr,
            }
            if summary.shell_result
            else None,
            "actions": [action.__dict__ for action in summary.actions],
        }
        print(json.dumps(payload, indent=2))
    else:
        print("Task executed in prototype mode.")
        print(f"Scanned {summary.files_scanned} files in {summary.repo_root}.")
        if summary.shell_result:
            print(f"Command output:\n{summary.shell_result.stdout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
