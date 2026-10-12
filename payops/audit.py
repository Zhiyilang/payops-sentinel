"""PayOpsSentinel - append-only audit log (JSONL).

Every observation, incident, decision, approval and executed action lands
here with a UTC timestamp. This file is the compliance artifact finance-ops
teams will ask for first, and the demo evidence judges can inspect.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .models import AuditEntry


class JsonlAuditor:
    def __init__(self, path: str = "payops_audit.jsonl"):
        self.path = path
        self._entries: list[AuditEntry] = []

    def log(self, event: str, payload: dict) -> AuditEntry:
        entry = AuditEntry(
            ts=datetime.now(timezone.utc).isoformat(),
            event=event,
            payload=payload,
        )
        self._entries.append(entry)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)
