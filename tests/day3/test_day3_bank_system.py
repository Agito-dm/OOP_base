import pytest
from datetime import datetime

from src.day1.exceptions.exceptions import InvalidOperationError, AccountFrozenError
from src.day1.model.abstract_account import Currency, AccountStatus
from src.day3.bank import Bank
from src.day3.model.client import Client, ClientStatus


def test_client_age_validation() -> None:
    with pytest.raises(InvalidOperationError):
        Client(full_name="Teen User", age=17, contacts={"email": "t@x.com"})


def test_auth_lockout_after_three_failures() -> None:
    bank = Bank()
    client = Client(full_name="Ivan Petrov", age=25, contacts={"email": "ivan@x.com"})
    cid = bank.add_client(client, password="1234")

    assert bank.authenticate_client(cid, "wrong") is False
    assert bank.authenticate_client(cid, "wrong") is False
    assert bank.authenticate_client(cid, "wrong") is False

    assert bank.clients[cid].status == ClientStatus.BLOCKED
    assert bank.authenticate_client(cid, "1234") is False  # уже заблокирован

    # должны быть подозрительные события
    assert any(e.client_id == cid and e.action == "auth" for e in bank.suspicious_events)


def test_open_accounts_freeze_and_withdraw_blocked() -> None:
    bank = Bank()
    client = Client(full_name="Dmitry S", age=30, contacts={"email": "d@x.com"})
    cid = bank.add_client(client, password="pass")

    acc_id = bank.open_account(cid, account_type="bank", balance=1000, currency=Currency.RUB)
    bank.freeze_account(cid, acc_id)

    # withdraw через банк дергает acc.withdraw, а там будет AccountFrozenError
    with pytest.raises(AccountFrozenError):
        bank.withdraw(cid, acc_id, 100)


def test_quiet_hours_block_money_operations_and_mark_suspicious() -> None:
    def fake_time() -> datetime:
        return datetime(2026, 3, 11, 1, 0, 0)  # 01:00 тихие часы

    bank = Bank(time_provider=fake_time)
    client = Client(full_name="Night User", age=22, contacts={"email": "n@x.com"})
    cid = bank.add_client(client, password="pass")

    acc_id = bank.open_account(cid, account_type="bank", balance=1000, currency=Currency.USD)

    with pytest.raises(InvalidOperationError):
        bank.deposit(cid, acc_id, 100)

    assert any(e.client_id == cid and e.reason.startswith("Попытка операции") for e in bank.suspicious_events)


def test_total_balance_and_ranking() -> None:
    bank = Bank()

    c1 = Client(full_name="Alice A", age=28, contacts={"email": "a@x.com"})
    c2 = Client(full_name="Bob B", age=35, contacts={"email": "b@x.com"})
    id1 = bank.add_client(c1, password="1111")
    id2 = bank.add_client(c2, password="2222")

    a1 = bank.open_account(id1, account_type="bank", balance=500)
    a2 = bank.open_account(id2, account_type="bank", balance=1500)

    assert bank.get_total_balance() == 2000.0

    ranking = bank.get_clients_ranking()
    assert ranking[0][0] == id2  # Bob выше, баланс больше
