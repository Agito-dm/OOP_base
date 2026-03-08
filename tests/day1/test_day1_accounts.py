import pytest

from src.day1.exceptions.exceptions import AccountFrozenError
from src.day1.model.abstract_account import AccountStatus, Currency, Owner
from src.day1.model.bank_account import BankAccount


def test_create_active_account_and_deposit_withdraw() -> None:
    owner = Owner(name="Dmitry", contact="dmitry@example.com")
    account = BankAccount(owner=owner, balance=1000, currency=Currency.RUB)

    account.deposit(500)
    assert account.get_account_info()["balance"] == 1500.0

    account.withdraw(200)
    assert account.get_account_info()["balance"] == 1300.0


def test_frozen_account_forbids_operations() -> None:
    owner = Owner(name="Dmitry", contact="dmitry@example.com")
    account = BankAccount(owner=owner, balance=1000, status=AccountStatus.FROZEN)

    with pytest.raises(AccountFrozenError):
        account.deposit(100)

    with pytest.raises(AccountFrozenError):
        account.withdraw(100)


def test_str_contains_last4_status_balance_currency() -> None:
    owner = Owner(name="Dmitry", contact="dmitry@example.com")
    account = BankAccount(owner=owner, account_id="ABCDEF123456", balance=10, currency=Currency.USD)

    text = str(account)

    assert "BankAccount" in text
    assert "Dmitry" in text
    assert "****3456" in text
    assert "active" in text
    assert "10.00 USD" in text