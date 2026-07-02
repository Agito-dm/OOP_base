from __future__ import annotations

from datetime import datetime, timedelta

from src.day1.model.abstract_account import Currency
from src.day3.bank import Bank
from src.day3.model.client import Client, ClientStatus
from src.day4.model.transaction import Transaction, TransactionType, TransactionStatus
from src.day4.queue import TransactionQueue
from src.day4.processor import TransactionProcessor


def test_day4_transactions_queue_and_processing() -> None:
    # управляем временем вручную
    current = {"now": datetime(2026, 3, 18, 10, 0, 0)}

    def now() -> datetime:
        return current["now"]

    bank = Bank(time_provider=now)

    # создание клиентов и счета
    c1 = Client(full_name="Alice A", age=28, contacts={"email": "a@x.com"})
    c2 = Client(full_name="Bob B", age=35, contacts={"email": "b@x.com"})
    id1 = bank.add_client(c1, password="1111")
    id2 = bank.add_client(c2, password="2222")

    a1 = bank.open_account(id1, account_type="bank", balance=5000, currency=Currency.RUB)
    a2 = bank.open_account(id2, account_type="bank", balance=1000, currency=Currency.USD)
    a3 = bank.open_account(id1, account_type="premium", balance=100, currency=Currency.RUB, overdraft_limit=500, withdraw_fee=0)

    # специальный счет с маленьким балансом для проверки отказа при недостатке средств
    a_low_balance = bank.open_account(id1, account_type="bank", balance=1, currency=Currency.RUB)

    # заморозка одного счета, чтобы показать ретраи
    bank.freeze_account(id1, a1)

    queue = TransactionQueue(time_provider=now)
    processor = TransactionProcessor(bank, queue, time_provider=now, max_attempts=3)

    txs = []

    # замороженный отправитель сначала упадёт, потом ретрай + успех после разморозки
    txs.append(Transaction(TransactionType.INTERNAL_TRANSFER, 100, Currency.RUB, sender_account_id=a1, recipient_account_id=a2, priority=5))

    # приоритет высокий
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 50, Currency.RUB, sender_account_id=a3, recipient_account_id=None, priority=10))

    # с конвертацией amount задан в USD, получатель в RUB
    txs.append(Transaction(TransactionType.INTERNAL_TRANSFER, 10, Currency.USD, sender_account_id=a2, recipient_account_id=a3, priority=1))

    # отказ при недостатке средств на обычном счёте
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.RUB, sender_account_id=a_low_balance, recipient_account_id=None, priority=1))

    # delayed internal через 1 час
    txs.append(Transaction(TransactionType.INTERNAL_TRANSFER, 200, Currency.RUB, sender_account_id=a3, recipient_account_id=a2, priority=2))

    # отмененная транзакция
    tx_cancel = Transaction(TransactionType.INTERNAL_TRANSFER, 30, Currency.RUB, sender_account_id=a3, recipient_account_id=a2, priority=3)
    txs.append(tx_cancel)

    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 20, Currency.RUB, sender_account_id=a3, priority=0))
    txs.append(Transaction(TransactionType.INTERNAL_TRANSFER, 15, Currency.USD, sender_account_id=a2, recipient_account_id=a3, priority=0))
    txs.append(Transaction(TransactionType.INTERNAL_TRANSFER, 10, Currency.RUB, sender_account_id=a3, recipient_account_id=a2, priority=0))
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.USD, sender_account_id=a2, priority=0))

    # очередь
    for i, tx in enumerate(txs):
        if tx is txs[4]:
            queue.add(tx, priority=tx.priority, run_at=now() + timedelta(hours=1))
        else:
            queue.add(tx, priority=tx.priority)

    # отмена одной
    queue.cancel(tx_cancel.tx_id, reason="user canceled")

    # замороженный отправитель даст ошибку и уйдёт на ретрай
    done1 = processor.process_all_ready()
    assert len(done1) > 0

    # разморозка счета, чтобы ретрай смог пройти
    bank.unfreeze_account(id1, a1)

    # сдвиг времени, чтобы ретрай стал готов
    current["now"] = current["now"] + timedelta(minutes=2)
    done2 = processor.process_all_ready()

    # отложенная транзакция еще не должна выполниться
    assert processor.queue.get(txs[4].tx_id).status in (TransactionStatus.QUEUED, TransactionStatus.PENDING)

    # сдвиг времени на 2 часа
    current["now"] = current["now"] + timedelta(hours=2)
    done3 = processor.process_all_ready()

    status_map = {tx.tx_id: tx.status for tx in txs}

    assert status_map[tx_cancel.tx_id] == TransactionStatus.CANCELED
    assert status_map[txs[3].tx_id] == TransactionStatus.FAILED  # недостаточно средств
    assert txs[3].decline_reason is not None
    assert "Недостаточно средств" in txs[3].decline_reason
    assert status_map[txs[4].tx_id] == TransactionStatus.COMPLETED  # delayed

    # после разморозки должна завершиться успешно
    assert status_map[txs[0].tx_id] == TransactionStatus.COMPLETED

    # 10 транзакций в системе
    assert len(queue) == 10

    # должны быть ошибки в логе
    assert len(processor.error_log) >= 1


def test_internal_transfer_is_atomic_when_recipient_client_blocked() -> None:
    current = {"now": datetime(2026, 3, 18, 10, 0, 0)}

    def now() -> datetime:
        return current["now"]

    bank = Bank(time_provider=now)

    sender = Client(full_name="Sender User", age=30, contacts={"email": "sender@x.com"})
    recipient = Client(full_name="Recipient User", age=31, contacts={"email": "recipient@x.com"})

    sender_id = bank.add_client(sender, password="1111")
    recipient_id = bank.add_client(recipient, password="2222")

    sender_acc_id = bank.open_account(sender_id, account_type="bank", balance=1000, currency=Currency.RUB)
    recipient_acc_id = bank.open_account(recipient_id, account_type="bank", balance=100, currency=Currency.RUB)

    sender_balance_before = bank.accounts[sender_acc_id].get_account_info()["balance"]
    recipient_balance_before = bank.accounts[recipient_acc_id].get_account_info()["balance"]

    # Получатель заблокирован deposit на его счёт должен упасть
    bank.clients[recipient_id].status = ClientStatus.BLOCKED

    queue = TransactionQueue(time_provider=now)
    processor = TransactionProcessor(bank, queue, time_provider=now, max_attempts=1)

    tx = Transaction(
        TransactionType.INTERNAL_TRANSFER,
        100,
        Currency.RUB,
        sender_account_id=sender_acc_id,
        recipient_account_id=recipient_acc_id,
        priority=1,
    )

    queue.add(tx, priority=tx.priority)

    processed = processor.process_next()

    assert processed is tx
    assert tx.status == TransactionStatus.FAILED
    assert tx.decline_reason is not None
    assert "Клиент заблокирован" in tx.decline_reason

    assert bank.accounts[sender_acc_id].get_account_info()["balance"] == sender_balance_before
    assert bank.accounts[recipient_acc_id].get_account_info()["balance"] == recipient_balance_before
