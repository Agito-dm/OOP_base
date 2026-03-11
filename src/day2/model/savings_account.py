"""
Day2: SavingsAccount с минимальным остатком и ежемесячным процентом
"""

from __future__ import annotations

from typing import Any, Dict

from src.day1.exceptions.exceptions import InvalidOperationError
from src.day1.model.bank_account import BankAccount
from src.day1.model.abstract_account import AccountStatus


class SavingsAccount(BankAccount):
    def __init__(
        self,
        *args,
        min_balance: float = 0.0,
        monthly_interest_rate: float = 0.0,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        if min_balance < 0:
            raise InvalidOperationError("min_balance не может быть отрицательным.")
        if monthly_interest_rate < 0:
            raise InvalidOperationError("monthly_interest_rate не может быть отрицательной.")

        self.min_balance = float(min_balance)
        self.monthly_interest_rate = float(monthly_interest_rate)

    def apply_monthly_interest(self) -> None:
        """
        Начисление процентов за месяц.
        """
        # защита статусов как в BankAccount
        self._ensure_can_operate()

        interest = self._balance * self.monthly_interest_rate
        if interest > 0:
            self._balance += interest

    def withdraw(self, amount: float) -> None:
        """
        Нельзя уйти ниже min_balance.
        """
        self._ensure_can_operate()
        value = self._validate_amount(amount)

        if self._balance - value < self.min_balance:
            raise InvalidOperationError("Нельзя опуститься ниже минимального остатка (min_balance).")

        self._balance -= value

    def get_account_info(self) -> Dict[str, Any]:
        info = super().get_account_info()
        info.update(
            {
                "type": "savings",
                "min_balance": self.min_balance,
                "monthly_interest_rate": self.monthly_interest_rate,
            }
        )
        return info

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base} | min_balance={self.min_balance:.2f} | monthly_rate={self.monthly_interest_rate:.4f}"
