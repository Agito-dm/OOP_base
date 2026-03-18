"""
Day3: Client — клиент банка.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from src.day1.exceptions.exceptions import InvalidOperationError


class ClientStatus(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


@dataclass
class Client:
    """
    Клиент банка.

    Требования:
    - ФИО, ID, статус
    - список номеров счетов
    - контакты
    - проверка возраста >= 18
    """
    full_name: str
    age: int
    contacts: dict[str, str]
    client_id: str | None = None

    status: ClientStatus = ClientStatus.ACTIVE
    account_ids: list[str] = field(default_factory=list)

    failed_auth_attempts: int = 0  # для правила "3 неверные попытки = блокировка"

    def __post_init__(self) -> None:
        if self.age < 18:
            raise InvalidOperationError("Клиент должен быть старше или равен 18 годам.")
        if not self.client_id:
            self.client_id = uuid.uuid4().hex[:8]

    def register_failed_attempt(self) -> None:
        self.failed_auth_attempts += 1
        if self.failed_auth_attempts >= 3:
            self.status = ClientStatus.BLOCKED

    def reset_failed_attempts(self) -> None:
        self.failed_auth_attempts = 0
