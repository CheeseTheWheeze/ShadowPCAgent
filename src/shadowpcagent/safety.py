from dataclasses import dataclass

from shadowpcagent.models import Plan


SENSITIVE_KEYWORDS = {
    "secret",
    "token",
    "password",
    "auth",
    "deploy",
    "production",
    "credential",
    "security",
    "permission",
    "policy",
}

SENSITIVE_PATH_PARTS = {
    ".env",
    "secrets",
    "credentials",
    "production",
    "deploy",
    "auth",
    "token",
}


@dataclass
class SafetyReport:
    requires_approval: bool
    reasons: list[str]
    draft_diff: str


class SafetyEngine:
    def classify(self, task: str, plan: Plan) -> SafetyReport:
        reasons = self._match_keywords(task)
        requires_approval = len(reasons) > 0
        draft_diff = self._draft_diff(task, plan) if requires_approval else ""
        return SafetyReport(
            requires_approval=requires_approval,
            reasons=reasons,
            draft_diff=draft_diff,
        )

    def is_sensitive_path(self, path: str) -> bool:
        lowered = path.lower()
        return any(part in lowered for part in SENSITIVE_PATH_PARTS)

    def _match_keywords(self, task: str) -> list[str]:
        tokens = {token.strip(".,").lower() for token in task.split()}
        matches = sorted(SENSITIVE_KEYWORDS.intersection(tokens))
        return [f"Matched sensitive keyword: {keyword}" for keyword in matches]

    def _draft_diff(self, task: str, plan: Plan) -> str:
        return "\n".join(
            [
                "--- draft/placeholder.txt",
                "+++ draft/placeholder.txt",
                "@@ -0,0 +1,5 @@",
                f"+Task: {task}",
                f"+Plan steps: {len(plan.steps)}",
                "+Notes: Sensitive changes detected.",
                "+Approval required before applying changes.",
            ]
        )
