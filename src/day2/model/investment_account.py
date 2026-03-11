"""
Day2: InvestmentAccount портфель виртуальных активов + прогноз роста
"""

from __future__ import annotations

from typing import Any, Dict

from src.day1.exceptions.exceptions import InvalidOperationError
from src.day1.model.bank_account import BankAccount


class InvestmentAccount(BankAccount):
    DEFAULT_YEARLY_RATES = {
        "stocks": 0.08,
        "bonds": 0.04,
        "etf": 0.06,
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # храним портфель как тип актива - (название - инвестированная сумма)
        self.portfolio: Dict[str, Dict[str, float]] = {
            "stocks": {},
            "bonds": {},
            "etf": {},
        }

    def invest(self, asset_type: str, name: str, amount: float) -> None:
        """
        Переводим часть денег со счета в виртуальный актив
        amount — именно сумма денег (без цен и лотов, упрощенно)
        """
        self._ensure_can_operate()
        value = self._validate_amount(amount)

        if asset_type not in self.portfolio:
            raise InvalidOperationError("asset_type должен быть одним из: stocks, bonds, etf.")

        # инвестирование = уменьшить кэш-баланс + увеличить запись в портфеле
        # используем базовую логику списания без овердрафта (BankAccount.withdraw)
        super().withdraw(value)

        self.portfolio[asset_type][name] = self.portfolio[asset_type].get(name, 0.0) + value

    def withdraw(self, amount: float) -> None:
        """
        Для инвестиционного счета: снимаем только из "кэша" (баланса)
        Активы не ликвидируем автоматически (упрощение)
        """
        super().withdraw(amount)

    def project_yearly_growth(self, years: int = 1) -> Dict[str, Any]:
        """
        Прогноз стоимости портфеля через N лет
        Возвращаем словарь с деталями
        """
        if years < 0:
            raise InvalidOperationError("years не может быть отрицательным.")

        projected_by_type: Dict[str, float] = {}
        total = 0.0

        for asset_type, items in self.portfolio.items():
            rate = self.DEFAULT_YEARLY_RATES.get(asset_type, 0.0)
            current_value = sum(items.values())
            projected_value = current_value * ((1 + rate) ** years)
            projected_by_type[asset_type] = projected_value
            total += projected_value

        return {
            "years": years,
            "projected_by_type": projected_by_type,
            "projected_portfolio_total": total,
        }

    def get_account_info(self) -> Dict[str, Any]:
        info = super().get_account_info()
        info.update(
            {
                "type": "investment",
                "portfolio": self.portfolio,
            }
        )
        return info

    def __str__(self) -> str:
        base = super().__str__()
        stocks_sum = sum(self.portfolio["stocks"].values())
        bonds_sum = sum(self.portfolio["bonds"].values())
        etf_sum = sum(self.portfolio["etf"].values())
        return f"{base} | portfolio: stocks={stocks_sum:.2f}, bonds={bonds_sum:.2f}, etf={etf_sum:.2f}"
