from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class AuditLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    timestamp: datetime
    level: AuditLevel
    message: str
    client_id: str | None = None
    tx_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    """
    AuditLog:
    - уровни важности
    - сохранение в память и файл
    - фильтрация
    """

    def __init__(self, file_path: str | Path | None = None) -> None:
        self.events: list[AuditEvent] = []
        self.file_path: Path | None = Path(file_path) if file_path else None

        if self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        level: AuditLevel,
        message: str,
        *,
        client_id: str | None = None,
        tx_id: str | None = None,
        meta: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        ts = timestamp or datetime.now()
        ev = AuditEvent(
            timestamp=ts,
            level=level,
            message=message,
            client_id=client_id,
            tx_id=tx_id,
            meta=meta or {},
        )
        self.events.append(ev)

        if self.file_path:
            line = {
                "timestamp": ev.timestamp.isoformat(),
                "level": ev.level.value,
                "message": ev.message,
                "client_id": ev.client_id,
                "tx_id": ev.tx_id,
                "meta": ev.meta,
            }
            self.file_path.open("a", encoding="utf-8").write(json.dumps(line, ensure_ascii=False) + "\n")

    def filter(
        self,
        *,
        level: AuditLevel | None = None,
        client_id: str | None = None,
        tx_id: str | None = None,
        contains: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        min_level: AuditLevel | None = None,
    ) -> list[AuditEvent]:
        """
        Фильтрация:
        - по уровню/минимальному уровню
        - по client_id/tx_id
        - по подстроке в message
        - по времени (since/until)
        """
        def level_rank(lv: AuditLevel) -> int:
            order = {
                AuditLevel.INFO: 0,
                AuditLevel.WARNING: 1,
                AuditLevel.ERROR: 2,
                AuditLevel.CRITICAL: 3,
            }
            return order[lv]

        out: list[AuditEvent] = []
        for ev in self.events:
            if level is not None and ev.level != level:
                continue
            if min_level is not None and level_rank(ev.level) < level_rank(min_level):
                continue
            if client_id is not None and ev.client_id != client_id:
                continue
            if tx_id is not None and ev.tx_id != tx_id:
                continue
            if contains is not None and contains.lower() not in ev.message.lower():
                continue
            if since is not None and ev.timestamp < since:
                continue
            if until is not None and ev.timestamp > until:
                continue
            out.append(ev)
        return out

    def error_stats(self) -> dict[str, int]:
        """
        Статистика ошибок по типу сообщения.
        Простой вариант: считаем события уровней ERROR/CRITICAL.
        """
        stats: dict[str, int] = {}
        for ev in self.events:
            if ev.level in (AuditLevel.ERROR, AuditLevel.CRITICAL):
                key = ev.message.split(":")[0].strip()
                stats[key] = stats.get(key, 0) + 1
        return stats
