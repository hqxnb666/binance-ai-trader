from __future__ import annotations

from sqlalchemy.orm import Session

from journal.models import RuntimeState

KILL_SWITCH_KEY = "kill_switch"


class CircuitBreaker:
    def __init__(self, session: Session):
        self.session = session

    def is_enabled(self) -> bool:
        record = self.session.get(RuntimeState, KILL_SWITCH_KEY)
        if record is None:
            return False
        return bool(record.value_json.get("enabled", False))

    def set_enabled(self, enabled: bool) -> RuntimeState:
        record = self.session.get(RuntimeState, KILL_SWITCH_KEY)
        if record is None:
            record = RuntimeState(key=KILL_SWITCH_KEY, value_json={"enabled": enabled})
            self.session.add(record)
        else:
            record.value_json = {"enabled": enabled}
        self.session.flush()
        return record

