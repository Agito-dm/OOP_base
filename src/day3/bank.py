"""
Day3: Bank — управляющий класс банка (клиенты, счета, безопасность).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable, Optional, Type

from src.day1.exceptions.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)
from src.day1.model.abstract_account import AccountStatus, Currency, Owner
from src.day1.model.bank_account import BankAccount
from src.day2.model.investment_account import InvestmentAccount
from src.day2.model.premium_account import PremiumAccount
from src.day2.model.savings_account import SavingsAccount
from src.day3.model.client import Client, ClientStatus


@dataclass
class SuspiciousEvent:
    timestamp: datetime
    client_id: str
    action: str
    reason: str


class Bank:
    """
    Управляющий класс банка.

    Требования:
    - add_client, open_account, close_account, freeze/unfreeze, authenticate_client, search_accounts
    - защита: 3 неверные попытки = блокировка
    - пометка подозрительных действий
    - запрет операций с 00:00 до 05:00 (ниже применяем к денежным операциям)
    - дополнительно: get_total_balance, get_clients_ranking
    """

    def __init__(self, time_provider: Optional[Callable[[], datetime]] = None) -> None:
        self._time_provider = time_provider or datetime.now

        self.clients: dict[str, Client] = {}
        self._passwords: dict[str, str] = {}

        self.accounts: dict[str, BankAccount] = {}
        self._account_owner: dict[str, str] = {}  # account_id - client_id

        self.suspicious_events: list[SuspiciousEvent] = []

    # security helpers
    def _now(self) -> datetime:
        return self._time_provider()

    def _is_quiet_hours(self) -> bool:
        """
        Тихие часы: с 00:00 до 05:00.
        """
        current = self._now().time()
        return time(0, 0) <= current < time(5, 0)

    def _mark_suspicious(self, client_id: str, action: str, reason: str) -> None:
        self.suspicious_events.append(
            SuspiciousEvent(
                timestamp=self._now(),
                client_id=client_id,
                action=action,
                reason=reason,
            )
        )

    def _ensure_client_exists(self, client_id: str) -> Client:
        client = self.clients.get(client_id)
        if not client:
            raise InvalidOperationError("Клиент не найден.")
        return client

    def _ensure_client_active(self, client: Client) -> None:
        if client.status == ClientStatus.BLOCKED:
            raise InvalidOperationError("Клиент заблокирован.")

    def _ensure_owns_account(self, client_id: str, account_id: str) -> None:
        owner_id = self._account_owner.get(account_id)
        if owner_id != client_id:
            self._mark_suspicious(client_id, "access_account", f"Попытка доступа к чужому счёту {account_id}.")
            raise InvalidOperationError("Счёт не принадлежит клиенту.")

    def _ensure_money_operations_allowed(self, client_id: str, action: str) -> None:
        """
        Запрет денежных операций в тихие часы.
        """
        if self._is_quiet_hours():
            self._mark_suspicious(client_id, action, "Попытка операции в тихие часы (00:00–05:00).")
            raise InvalidOperationError("Операции запрещены с 00:00 до 05:00.")

    # API from requirements
    def add_client(self, client: Client, password: str) -> str:
        if not password or len(password) < 4:
            raise InvalidOperationError("Пароль должен быть минимум 4 символа.")
        if client.client_id in self.clients:
            raise InvalidOperationError("Клиент с таким ID уже существует.")

        self.clients[client.client_id] = client
        self._passwords[client.client_id] = password
        return client.client_id

    def authenticate_client(self, client_id: str, password: str) -> bool:
        client = self._ensure_client_exists(client_id)

        # если уже заблокирован, то фиксируем как подозрительное
        if client.status == ClientStatus.BLOCKED:
            self._mark_suspicious(client_id, "auth", "Попытка входа заблокированного клиента.")
            return False

        ok = self._passwords.get(client_id) == password # вместо хэша
        if ok:
            client.reset_failed_attempts()
            return True

        client.register_failed_attempt()
        if client.status == ClientStatus.BLOCKED:
            self._mark_suspicious(client_id, "auth", "3 неверные попытки входа, клиент заблокирован.")
        return False

    def open_account(
        self,
        client_id: str,
        account_type: str = "bank",
        *,
        currency: Currency = Currency.RUB,
        balance: float = 0.0,
        **kwargs,
    ) -> str:
        client = self._ensure_client_exists(client_id)
        self._ensure_client_active(client)

        account_cls: Type[BankAccount]
        mapping: dict[str, Type[BankAccount]] = {
            "bank": BankAccount,
            "savings": SavingsAccount,
            "premium": PremiumAccount,
            "investment": InvestmentAccount,
        }
        account_cls = mapping.get(account_type)
        if not account_cls:
            raise InvalidOperationError("Неизвестный account_type. Используй: bank/savings/premium/investment.")

        # Owner из Day1 для счета
        primary_contact = client.contacts.get("email") or client.contacts.get("phone") or "n/a"
        owner = Owner(name=client.full_name, contact=primary_contact)

        account = account_cls(owner=owner, balance=balance, currency=currency, **kwargs)

        # защита от коллизий id
        if account.id in self.accounts:
            raise InvalidOperationError(f"Account id '{account.id}' already exists.")

        self.accounts[account.id] = account
        self._account_owner[account.id] = client_id
        client.account_ids.append(account.id)

        return account.id

    def close_account(self, client_id: str, account_id: str) -> None:
        client = self._ensure_client_exists(client_id)
        self._ensure_client_active(client)
        self._ensure_owns_account(client_id, account_id)

        acc = self.accounts.get(account_id)
        if not acc:
            raise InvalidOperationError("Счёт не найден.")

        acc.status = AccountStatus.CLOSED

    def freeze_account(self, client_id: str, account_id: str) -> None:
        client = self._ensure_client_exists(client_id)
        self._ensure_client_active(client)
        self._ensure_owns_account(client_id, account_id)

        acc = self.accounts.get(account_id)
        if not acc:
            raise InvalidOperationError("Счёт не найден.")
        if acc.status == AccountStatus.CLOSED:
            raise AccountClosedError("Нельзя заморозить закрытый счёт.")

        acc.status = AccountStatus.FROZEN

    def unfreeze_account(self, client_id: str, account_id: str) -> None:
        client = self._ensure_client_exists(client_id)
        self._ensure_client_active(client)
        self._ensure_owns_account(client_id, account_id)

        acc = self.accounts.get(account_id)
        if not acc:
            raise InvalidOperationError("Счёт не найден.")
        if acc.status == AccountStatus.CLOSED:
            raise AccountClosedError("Нельзя разморозить закрытый счёт.")

        acc.status = AccountStatus.ACTIVE

    def _normalize_account_type(self, t: str) -> str:
        t = t.strip().lower()
        return t.removesuffix("account")

    def search_accounts(
        self,
        *,
        client_id: str | None = None,
        status: AccountStatus | None = None,
        currency: Currency | None = None,
        account_type: str | None = None,
    ) -> list[BankAccount]:
        result: list[BankAccount] = []

        for acc_id, acc in self.accounts.items():
            if client_id is not None and self._account_owner.get(acc_id) != client_id:
                continue
            if status is not None and acc.status != status:
                continue
            if currency is not None and acc.currency != currency:
                continue
            if account_type is not None:
                if self._normalize_account_type(acc.__class__.__name__) != self._normalize_account_type(account_type):
                    continue
            result.append(acc)

        return result

    def deposit(self, client_id: str, account_id: str, amount: float) -> None:
        client = self._ensure_client_exists(client_id)
        self._ensure_client_active(client)

        self._ensure_owns_account(client_id, account_id)
        self._ensure_money_operations_allowed(client_id, "deposit")

        acc = self.accounts[account_id]
        acc.deposit(amount)

    def withdraw(self, client_id: str, account_id: str, amount: float) -> None:
        client = self._ensure_client_exists(client_id)
        self._ensure_client_active(client)

        self._ensure_owns_account(client_id, account_id)
        self._ensure_money_operations_allowed(client_id, "withdraw")

        acc = self.accounts[account_id]
        acc.withdraw(amount)

    # сумма баланса счетов без закрытых
    def get_total_balance(self, *, include_closed: bool = False) -> float:
        total = 0.0
        for acc in self.accounts.values():
            if not include_closed and acc.status == AccountStatus.CLOSED:
                continue
            total += acc.get_account_info()["balance"]
        return float(total)

    def get_clients_ranking(self) -> list[tuple[str, float]]:
        """
        Рейтинг клиентов по суммарному балансу их счетов (без закрытых).
        """
        sums: dict[str, float] = {cid: 0.0 for cid in self.clients.keys()}

        for acc_id, acc in self.accounts.items():
            if acc.status == AccountStatus.CLOSED:
                continue
            cid = self._account_owner.get(acc_id)
            if cid:
                sums[cid] += acc.get_account_info()["balance"]

        return sorted(sums.items(), key=lambda x: x[1], reverse=True)
