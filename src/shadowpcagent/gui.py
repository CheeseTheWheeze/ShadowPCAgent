from dataclasses import dataclass
from datetime import datetime


@dataclass
class GuiActionResult:
    action: str
    succeeded: bool
    timestamp: str


class GuiExecutor:
    def perform_action(self, action: str) -> GuiActionResult:
        timestamp = datetime.utcnow().isoformat() + "Z"
        return GuiActionResult(action=action, succeeded=True, timestamp=timestamp)
