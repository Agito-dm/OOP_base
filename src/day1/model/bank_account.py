"""
Day1: Конкретная реализация банковского счёта.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict

from src.day1.exceptions.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)
from src.day1.model.abstract_account import AbstractAccount, AccountStatus, Currency, Owner


class BankAccount(AbstractAccount):
    """
    Конкретный банковский счёт.

    Требования Day1:
    - валидация входящих данных
    - запрет операций при неверном статусе
    - короткий UUID, если account_id не передан
    - валюта из набора: RUB, USD, EUR, KZT, CNY
    """

    def __init__(
        self,
        owner: Owner,
        account_id: str | None = None,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
    ) -> None:
        if not account_id:
            account_id = uuid.uuid4().hex[:8]

        super().__init__(
            account_id=account_id,
            owner=owner,
            balance=balance,
            status=status,
            currency=currency,
        )

        if not isinstance(self.status, AccountStatus):
            raise InvalidOperationError("Некорректный статус счёта.")
        if not isinstance(self.currency, Currency):
            raise InvalidOperationError("Некорректная валюта счёта.")

    def _ensure_can_operate(self) -> None:
        """
        Проверка статуса счёта перед любой операцией.
        """
        if self.status == AccountStatus.FROZEN:
            raise AccountFrozenError("Счёт заморожен. Операция запрещена.")
        if self.status == AccountStatus.CLOSED:
            raise AccountClosedError("Счёт закрыт. Операция запрещена.")

    @staticmethod
    def _validate_amount(amount: float) -> float:
        """
        Проверка суммы:
        - должна быть числом
        - должна быть > 0
        """
        try:
            value = float(amount)
        except (TypeError, ValueError):
            raise InvalidOperationError("Сумма должна быть числом.")

        if value <= 0:
            raise InvalidOperationError("Сумма должна быть положительной и больше нуля.")

        return value

    def deposit(self, amount: float) -> None:
        self._ensure_can_operate()
        value = self._validate_amount(amount)
        self._balance += value

    def withdraw(self, amount: float) -> None:
        self._ensure_can_operate()
        value = self._validate_amount(amount)

        if value > self._balance:
            raise InsufficientFundsError("Недостаточно средств.")

        self._balance -= value

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "owner": {
                "name": self.owner.name,
                "contact": self.owner.contact,
            },
            "status": self.status.value,
            "balance": self._balance,
            "currency": self.currency.value,
        }