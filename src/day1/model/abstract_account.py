"""
Day1: Абстрактная модель банковского счёта.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class Currency(Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


@dataclass
class Owner:
    """
    Данные владельца счёта.
    Минимально: храним имя и контакт.
    """
    name: str
    contact: str


class AbstractAccount(ABC):
    """
    Абстрактный банковский счёт.

    Содержит:
    - уникальный идентификатор (id)
    - владельца (owner)
    - защищённый баланс (_balance)
    - статус (status)
    - валюту (currency)
    """

    def __init__(
        self,
        account_id: str,
        owner: Owner,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
    ) -> None:
        self.id = account_id
        self.owner = owner
        self._balance = float(balance)
        self.status = status
        self.currency = currency

    @abstractmethod
    def deposit(self, amount: float) -> None:
        """Пополнение счёта."""

    @abstractmethod
    def withdraw(self, amount: float) -> None:
        """Снятие средств."""

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """Информация о счёте в виде словаря."""

    def __str__(self) -> str:
        account_type = self.__class__.__name__
        client = self.owner.name
        last4 = str(self.id)[-4:]
        return (
            f"{account_type} | {client} | ****{last4} | "
            f"{self.status.value} | {self._balance:.2f} {self.currency.value}"
        )
