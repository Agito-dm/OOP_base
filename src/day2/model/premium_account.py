"""
Day2: PremiumAccount увеличенные лимиты, овердрафт, фиксированная комиссия.
"""

from __future__ import annotations

from typing import Any, Dict

from src.day1.exceptions.exceptions import InsufficientFundsError, InvalidOperationError
from src.day1.model.bank_account import BankAccount


class PremiumAccount(BankAccount):
    def __init__(
        self,
        *args,
        max_withdraw_per_operation: float = 500_000.0,
        overdraft_limit: float = 0.0,
        withdraw_fee: float = 0.0,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        if max_withdraw_per_operation <= 0:
            raise InvalidOperationError("max_withdraw_per_operation должен быть > 0.")
        if overdraft_limit < 0:
            raise InvalidOperationError("overdraft_limit не может быть отрицательным.")
        if withdraw_fee < 0:
            raise InvalidOperationError("withdraw_fee не может быть отрицательной.")

        self.max_withdraw_per_operation = float(max_withdraw_per_operation)
        self.overdraft_limit = float(overdraft_limit)
        self.withdraw_fee = float(withdraw_fee)

    def withdraw(self, amount: float) -> None:
        """
        Разрешаем уходить в минус до -overdraft_limit.
        Снимаем amount + фиксированная комиссия withdraw_fee.
        """
        self._ensure_can_operate()
        value = self._validate_amount(amount)

        if value > self.max_withdraw_per_operation:
            raise InvalidOperationError("Превышен лимит снятия за одну операцию.")

        total = value + self.withdraw_fee
        # можно уйти в минус, но не ниже -overdraft_limit
        if self._balance - total < -self.overdraft_limit:
            raise InsufficientFundsError("Недостаточно средств с учетом овердрафта и комиссии.")

        self._balance -= total

    def get_account_info(self) -> Dict[str, Any]:
        info = super().get_account_info()
        info.update(
            {
                "type": "premium",
                "max_withdraw_per_operation": self.max_withdraw_per_operation,
                "overdraft_limit": self.overdraft_limit,
                "withdraw_fee": self.withdraw_fee,
            }
        )
        return info

    def __str__(self) -> str:
        base = super().__str__()
        return (
            f"{base} | overdraft={self.overdraft_limit:.2f} | "
            f"fee={self.withdraw_fee:.2f} | max_withdraw={self.max_withdraw_per_operation:.2f}"
        )
