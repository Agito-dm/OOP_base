from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.day1.model.abstract_account import Currency
from src.day3.bank import Bank
from src.day3.model.client import Client
from src.day4.model.transaction import Transaction, TransactionType
from src.day4.queue import TransactionQueue
from src.day5.audit import AuditLog
from src.day5.risk import RiskAnalyzer
from src.day5.secure_processor import SecureTransactionProcessor
from src.day7.report_builder import ReportBuilder


def test_day7_reports_and_charts(tmp_path) -> None:
    pytest.importorskip("matplotlib")

    # контроль времени
    current = {"now": datetime(2026, 3, 18, 1, 0, 0)}

    def now() -> datetime:
        return current["now"]

    bank = Bank(time_provider=now)

    c1 = Client(full_name="Alice A", age=28, contacts={"email": "a@x.com"})
    c2 = Client(full_name="Bob B", age=35, contacts={"email": "b@x.com"})
    id1 = bank.add_client(c1, password="1111")
    id2 = bank.add_client(c2, password="2222")

    a1 = bank.open_account(id1, account_type="bank", balance=5000, currency=Currency.USD)
    a2 = bank.open_account(id2, account_type="bank", balance=100, currency=Currency.USD)

    queue = TransactionQueue(time_provider=now)
    audit = AuditLog(tmp_path / "audit.jsonl")
    risk = RiskAnalyzer(time_provider=now, large_amount_usd=500.0, frequent_threshold=3)

    processor = SecureTransactionProcessor(
        bank,
        queue,
        time_provider=now,
        audit_log=audit,
        risk_analyzer=risk,
        max_attempts=2,
    )

    txs = [
        Transaction(TransactionType.INTERNAL_TRANSFER, 10, Currency.USD, sender_account_id=a1, recipient_account_id=a2, priority=1),
        Transaction(TransactionType.EXTERNAL_TRANSFER, 1000, Currency.USD, sender_account_id=a1, priority=5),  # high-risk
        Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.USD, sender_account_id=a1),
        Transaction(TransactionType.EXTERNAL_TRANSFER, 5, Currency.USD, sender_account_id=a1),
    ]

    for tx in txs:
        queue.add(tx, priority=tx.priority, run_at=now())

    # снимки баланса банка после каждой обработки
    rb = ReportBuilder(bank, transactions=txs, audit_log=audit, risk_analyzer=risk, output_dir=tmp_path / "reports")

    for _ in range(10):
        tx = processor.process_next()
        if tx is None:
            break
        rb.add_bank_balance_snapshot(timestamp=now())
        current["now"] = current["now"] + timedelta(minutes=1)

    bank_report = rb.build_bank_report(top_n=3)
    client_report = rb.build_client_report(id1)
    risk_report = rb.build_risk_report()

    p_json = rb.export_to_json(bank_report, "bank_report.json")
    assert p_json.exists() and p_json.stat().st_size > 0

    csv_paths = rb.export_to_csv("bank", bank_report)
    assert len(csv_paths) >= 1
    assert all(p.exists() and p.stat().st_size > 0 for p in csv_paths)

    chart_paths = rb.save_charts(bank_report=bank_report, risk_report=risk_report)
    assert len(chart_paths) >= 2
    assert all(p.exists() and p.stat().st_size > 0 for p in chart_paths)

    p_client = rb.export_to_json(client_report, "client_report.json")
    assert p_client.exists() and p_client.stat().st_size > 0

    p_risk = rb.export_to_json(risk_report, "risk_report.json")
    assert p_risk.exists() and p_risk.stat().st_size > 0
