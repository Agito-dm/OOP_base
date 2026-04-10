from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.day1.model.abstract_account import Currency
from src.day3.bank import Bank
from src.day3.model.client import Client
from src.day4.model.transaction import Transaction, TransactionType, TransactionStatus
from src.day4.queue import TransactionQueue
from src.day5.audit import AuditLog, AuditLevel
from src.day5.risk import RiskAnalyzer, RiskLevel
from src.day5.secure_processor import SecureTransactionProcessor


def test_day5_audit_risk_blocking_and_reports(tmp_path) -> None:
    current = {"now": datetime(2026, 3, 18, 1, 0, 0)}  # 01:00 -> ночь

    def now() -> datetime:
        return current["now"]

    bank = Bank(time_provider=now)

    c1 = Client(full_name="Alice A", age=28, contacts={"email": "a@x.com"})
    c2 = Client(full_name="Bob B", age=35, contacts={"email": "b@x.com"})
    id1 = bank.add_client(c1, password="1111")
    id2 = bank.add_client(c2, password="2222")

    a1 = bank.open_account(id1, account_type="bank", balance=10_000, currency=Currency.USD)
    a2 = bank.open_account(id2, account_type="bank", balance=100, currency=Currency.USD)

    queue = TransactionQueue(time_provider=now)

    audit_file = tmp_path / "audit.jsonl"
    audit = AuditLog(audit_file)

    # thresholds маленькие, чтобы в тесте получать риск
    risk = RiskAnalyzer(
        time_provider=now,
        large_amount_usd=500.0,
        frequent_window_minutes=10,
        frequent_threshold=3,
    )

    processor = SecureTransactionProcessor(
        bank,
        queue,
        time_provider=now,
        audit_log=audit,
        risk_analyzer=risk,
        max_attempts=2,
    )

    txs: list[Transaction] = []

    # ночной перевод на новый счет low или medium
    txs.append(Transaction(TransactionType.INTERNAL_TRANSFER, 10, Currency.USD, sender_account_id=a1, recipient_account_id=a2, priority=1))

    # крупная сумма ночью - блок
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 1000, Currency.USD, sender_account_id=a1, priority=5))

    # частые операции
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.USD, sender_account_id=a1))
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.USD, sender_account_id=a1))
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.USD, sender_account_id=a1))

    # после частых операций + ночь для блока
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.USD, sender_account_id=a1))

    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 1, Currency.USD, sender_account_id=a1))
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 1, Currency.USD, sender_account_id=a1))
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 1, Currency.USD, sender_account_id=a1))
    txs.append(Transaction(TransactionType.EXTERNAL_TRANSFER, 1, Currency.USD, sender_account_id=a1))

    for tx in txs:
        queue.add(tx, priority=tx.priority)

    done = processor.process_all_ready()
    assert len(done) > 0

    status_map = {tx.tx_id: tx.status for tx in txs}
    assert status_map[txs[1].tx_id] == TransactionStatus.FAILED
    assert status_map[txs[5].tx_id] == TransactionStatus.FAILED

    # подозрительные операции
    suspicious = risk.suspicious_operations(min_level=RiskLevel.MEDIUM)
    assert len(suspicious) >= 1

    profile = risk.client_risk_profile(id1)
    assert profile["max_risk"] in ("medium", "high")

    stats = audit.error_stats()
    assert any(k.startswith("HighRiskOperationError") for k in stats.keys())

    crit = audit.filter(min_level=AuditLevel.CRITICAL)
    assert len(crit) >= 1

    text = audit_file.read_text(encoding="utf-8")
    assert len(text.strip()) > 0
