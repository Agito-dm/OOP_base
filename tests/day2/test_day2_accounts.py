import pytest

from src.day1.exceptions.exceptions import InvalidOperationError, InsufficientFundsError
from src.day1.model.abstract_account import Owner, Currency, AccountStatus
from src.day2.model.savings_account import SavingsAccount
from src.day2.model.premium_account import PremiumAccount
from src.day2.model.investment_account import InvestmentAccount


def test_savings_min_balance_and_interest() -> None:
    owner = Owner(name="Dmitry", contact="d@example.com")
    acc = SavingsAccount(
        owner=owner,
        balance=1000,
        currency=Currency.RUB,
        min_balance=200,
        monthly_interest_rate=0.01,
    )

    acc.apply_monthly_interest()
    assert acc.get_account_info()["balance"] == 1010.0

    with pytest.raises(InvalidOperationError):
        acc.withdraw(900)  # 1010 - 900 = 110 < 200


def test_premium_overdraft_and_fee_and_limit() -> None:
    owner = Owner(name="Dmitry", contact="d@example.com")
    acc = PremiumAccount(
        owner=owner,
        balance=1000,
        overdraft_limit=500,
        withdraw_fee=10,
        max_withdraw_per_operation=2000,
    )

    acc.withdraw(1200)  # total=1210 => balance becomes -210 (allowed)
    assert acc.get_account_info()["balance"] == -210.0

    with pytest.raises(InvalidOperationError):
        acc.withdraw(3000)  # > max_withdraw_per_operation

    with pytest.raises(InsufficientFundsError):
        acc.withdraw(400)  # total=410 => -210-410=-620 < -500


def test_investment_portfolio_and_growth_projection() -> None:
    owner = Owner(name="Dmitry", contact="d@example.com")
    acc = InvestmentAccount(owner=owner, balance=10_000, currency=Currency.USD)

    acc.invest("stocks", "AAPL", 3000)
    acc.invest("bonds", "US10Y", 2000)

    info = acc.get_account_info()
    assert info["balance"] == 5000.0
    assert info["portfolio"]["stocks"]["AAPL"] == 3000.0
    assert info["portfolio"]["bonds"]["US10Y"] == 2000.0

    projection = acc.project_yearly_growth(years=1)
    assert projection["projected_portfolio_total"] > 5000.0  # портфель растет (по дефолтным rate)


def test_polymorphism_withdraw_for_different_accounts() -> None:
    owner = Owner(name="Dmitry", contact="d@example.com")

    accounts = [
        SavingsAccount(owner=owner, balance=1000, min_balance=0, monthly_interest_rate=0.0),
        PremiumAccount(owner=owner, balance=1000, overdraft_limit=0, withdraw_fee=0, max_withdraw_per_operation=500_000),
        InvestmentAccount(owner=owner, balance=1000),
    ]

    for acc in accounts:
        acc.withdraw(100)  # у всех есть withdraw, но реализация разная
        assert acc.get_account_info()["balance"] == 900.0
