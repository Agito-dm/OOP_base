from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.day1.model.abstract_account import Currency
from src.day3.bank import Bank
from src.day3.model.client import Client
from src.day4.model.transaction import Transaction, TransactionType, TransactionStatus
from src.day4.queue import TransactionQueue
from src.day5.audit import AuditLog, AuditLevel
from src.day5.risk import RiskAnalyzer, RiskLevel
from src.day5.secure_processor import SecureTransactionProcessor
from src.day7.report_builder import ReportBuilder


@dataclass
class SimClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, *, minutes: int = 0, hours: int = 0, days: int = 0) -> None:
        self.current = self.current + timedelta(days=days, hours=hours, minutes=minutes)


FIRST_NAMES = ["Alice", "Bob", "Dmitry", "Ivan", "Olga", "Sofia", "Max", "John", "Maria", "Egor"]
LAST_NAMES = ["Petrov", "Ivanov", "Smirnov", "Sidorov", "Kuznetsova", "Volkova", "Novak", "Brown", "Miller", "Kim"]


def make_password() -> str:
    return str(random.randint(1000, 9999))


def pick_currency() -> Currency:
    return random.choice([Currency.RUB, Currency.USD, Currency.EUR, Currency.KZT, Currency.CNY])


def create_clients(bank: Bank, n: int) -> list[str]:
    client_ids: list[str] = []
    for i in range(n):
        full_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        age = random.randint(18, 60)
        email = f"user{i}@example.com"
        client = Client(full_name=full_name, age=age, contacts={"email": email})
        cid = bank.add_client(client, password=make_password())
        client_ids.append(cid)
    return client_ids


def create_accounts(bank: Bank, client_ids: list[str], total_accounts: int) -> list[str]:
    """
    Создаем 10-15 счетов разных типов.
    """
    account_ids: list[str] = []
    types = ["bank", "savings", "premium", "investment"]

    for _ in range(total_accounts):
        cid = random.choice(client_ids)
        acc_type = random.choice(types)
        cur = pick_currency()

        # Балансы иногда отрицательные
        balance = random.choice([random.uniform(0, 5000), random.uniform(50, 15000), random.uniform(-200, 200)])

        kwargs = {}
        if acc_type == "savings":
            kwargs = {
                "min_balance": float(random.choice([0, 100, 200, 500])),
                "monthly_interest_rate": float(random.choice([0.0, 0.005, 0.01])),
            }
        elif acc_type == "premium":
            kwargs = {
                "max_withdraw_per_operation": float(random.choice([2000, 50000, 500_000])),
                "overdraft_limit": float(random.choice([0, 200, 500, 2000])),
                "withdraw_fee": float(random.choice([0, 1, 5, 10])),
            }

        acc_id = bank.open_account(
            cid,
            account_type=acc_type,
            balance=float(balance),
            currency=cur,
            **kwargs,
        )
        account_ids.append(acc_id)

    return account_ids


def pick_sender(accounts: list[str]) -> str:
    return random.choice(accounts)


def pick_recipient(accounts: list[str], sender: str) -> str:
    # выбираем другого
    choices = [a for a in accounts if a != sender]
    return random.choice(choices) if choices else sender


def generate_transactions(accounts: list[str], n: int, clock: SimClock) -> list[Transaction]:
    """
    Генерируем 30-50 транзакций:
    - часть обычных
    - часть ошибочных
    - часть подозрительных (крупные суммы / частые / новые получатели / ночью)
    """
    txs: list[Transaction] = []

    for i in range(n):
        tx_type = random.choice([TransactionType.INTERNAL_TRANSFER, TransactionType.EXTERNAL_TRANSFER])
        sender = pick_sender(accounts)

        # часть транзакций откладываются на будущее
        scheduled_for = None
        if random.random() < 0.20:
            scheduled_for = clock.now() + timedelta(minutes=random.choice([10, 30, 60, 120]))

        # приоритет
        priority = random.choice([0, 0, 1, 2, 5, 10])

        # валюта транзакции может отличаться от валюты счета
        tx_currency = pick_currency()

        roll = random.random()
        if roll < 0.06:
            amount = -random.uniform(1, 50) # ошибочная отрицательная
        elif roll < 0.14:
            amount = 0 # ошибочная нулевая
        elif roll < 0.20:
            amount = random.uniform(800, 5000) # крупные под риск
        else:
            amount = random.uniform(1, 200)

        if tx_type == TransactionType.INTERNAL_TRANSFER:
            # иногда ошибка - нет получателя
            if random.random() < 0.06:
                recipient = None
            else:
                recipient = pick_recipient(accounts, sender)

            tx = Transaction(
                tx_type=tx_type,
                amount=float(amount),
                currency=tx_currency,
                sender_account_id=sender,
                recipient_account_id=recipient,
                priority=priority,
                scheduled_for=scheduled_for,
            )
        else:
            tx = Transaction(
                tx_type=tx_type,
                amount=float(amount),
                currency=tx_currency,
                sender_account_id=sender,
                recipient_account_id=None, # по модели Day4
                priority=priority,
                scheduled_for=scheduled_for,
            )

        txs.append(tx)

    # специальная очень крупная и ночная транзакция
    sender = pick_sender(accounts)
    txs.append(
        Transaction(
            tx_type=TransactionType.EXTERNAL_TRANSFER,
            amount=10_000.0,
            currency=Currency.USD,
            sender_account_id=sender,
            priority=10,
            scheduled_for=clock.now(),
        )
    )

    return txs


def print_client_accounts(bank: Bank, client_id: str) -> None:
    accounts = bank.search_accounts(client_id=client_id)
    print(f"\n[SCENARIO] Accounts for client {client_id} ({len(accounts)}):")
    for acc in accounts:
        print("  -", str(acc))


def print_client_history(bank: Bank, client_id: str, all_txs: list[Transaction], limit: int = 10) -> None:
    # транзакции клиента
    owned_ids = {acc.id for acc in bank.search_accounts(client_id=client_id)}

    related = [
        tx for tx in all_txs
        if tx.sender_account_id in owned_ids or (tx.recipient_account_id in owned_ids if tx.recipient_account_id else False)
    ]

    related_sorted = sorted(related, key=lambda t: t.created_at, reverse=True)[:limit]
    print(f"\n[SCENARIO] Last {len(related_sorted)} transactions for client {client_id}:")
    for tx in related_sorted:
        print(f"  - {tx.tx_id} {tx.tx_type.value} {tx.amount:.2f} {tx.currency.value} status={tx.status.value}")


def print_suspicious(risk: RiskAnalyzer, min_level: RiskLevel = RiskLevel.MEDIUM, limit: int = 10) -> None:
    suspicious = risk.suspicious_operations(min_level=min_level)
    print(f"\n[REPORT] Suspicious operations >= {min_level.value}: {len(suspicious)} (show {min(limit, len(suspicious))})")
    for rec in suspicious[:limit]:
        codes = [f.code for f in rec.findings]
        print(f"  - tx={rec.tx_id} client={rec.client_id} risk={rec.risk_level.value} findings={codes}")


def print_tx_stats(txs: list[Transaction]) -> None:
    statuses = Counter(tx.status for tx in txs)
    fees_total = sum(tx.fee for tx in txs if tx.status == TransactionStatus.COMPLETED)

    print("\n[REPORT] Transaction statistics:")
    for st, cnt in sorted(statuses.items(), key=lambda x: x[0].value):
        print(f"  - {st.value}: {cnt}")
    print(f"  - total_fees_completed: {fees_total:.2f}")


def main() -> None:
    random.seed(42)

    # старт ночью для риска
    clock = SimClock(current=datetime(2026, 3, 18, 0, 30, 0))

    bank = Bank(time_provider=clock.now)

    print("[INIT] Creating clients...")
    client_ids = create_clients(bank, n=7) # 5-10

    print("[INIT] Opening accounts...")
    account_ids = create_accounts(bank, client_ids, total_accounts=12) # 10-15
    print(f"[INIT] Clients: {len(client_ids)}, Accounts: {len(account_ids)}")

    # Audit Risk Queue Processor
    audit = AuditLog("docs/audit_day6.jsonl")
    risk = RiskAnalyzer(
        time_provider=clock.now,
        large_amount_usd=2000.0, # порог крупной суммы
        frequent_window_minutes=10,
        frequent_threshold=6, # частые операции
    )
    queue = TransactionQueue(time_provider=clock.now)

    processor = SecureTransactionProcessor(
        bank,
        queue,
        time_provider=clock.now,
        audit_log=audit,
        risk_analyzer=risk,
        max_attempts=3,
    )

    # Тихие часы
    print("\n[SECURITY DEMO] Quiet hours bank operation attempt (00:00-05:00):")
    demo_cid = client_ids[0]
    demo_acc = bank.search_accounts(client_id=demo_cid)[0].id
    try:
        bank.deposit(demo_cid, demo_acc, 10)
        print("  - deposit succeeded (unexpected)")
    except Exception as e:
        print(f"  - deposit blocked: {type(e).__name__}: {e}")

    # Генерация 30-50 транзакций
    print("\n[SIM] Generating transactions...")
    txs = generate_transactions(account_ids, n=40, clock=clock)
    print(f"[SIM] Generated: {len(txs)} transactions")

    # Кладем в очередь, часть отменяем
    print("\n[QUEUE] Enqueue transactions...")
    cancel_count = 0
    for tx in txs:
        run_at = tx.scheduled_for
        queue.add(tx, priority=tx.priority, run_at=run_at)
        print(
            f"  - queued tx={tx.tx_id} type={tx.tx_type.value} amount={tx.amount:.2f} {tx.currency.value} "
            f"prio={tx.priority} run_at={(run_at.isoformat() if run_at else clock.now().isoformat())}"
        )

        # случайная отмена
        if cancel_count < 3 and random.random() < 0.03:
            queue.cancel(tx.tx_id, reason="demo cancel")
            cancel_count += 1

    # Симуляция обработки
    # часть пройдёт
    # часть упадёт (ошибки)
    # часть заблокируется как высокий риск
    rb = ReportBuilder(bank, transactions=txs, audit_log=audit, risk_analyzer=risk, output_dir="docs/reports")

    print("\n[PROCESS] Processing loop...")
    processed = 0
    max_steps = 1000

    for _ in range(max_steps):
        tx = processor.process_next()

        if tx is None:
            # если ничего не готового, то сдвиг
            clock.advance(minutes=30)
            # ограничение времеми
            if clock.now() > datetime(2026, 3, 19, 12, 0, 0):
                break
            continue

        processed += 1

        rb.add_bank_balance_snapshot(timestamp=clock.now())

        print(
            f"  - processed tx={tx.tx_id} status={tx.status.value} attempts={tx.attempts} "
            f"fee={tx.fee:.2f} reason={tx.decline_reason}"
        )

        # чтобы показать смену времени
        if processed == 10:
            clock.current = datetime(2026, 3, 18, 10, 0, 0)
            print(f"  [TIME] switched to daytime: {clock.now().isoformat()}")

    print(f"\n[PROCESS] Finished. Total processed events: {processed}")
    print(f"[AUDIT] Total audit events in memory: {len(audit.events)}")
    print(f"[AUDIT] Audit file: docs/audit_day6.jsonl")

    chosen_client = client_ids[0]
    print_client_accounts(bank, chosen_client)
    print_client_history(bank, chosen_client, txs, limit=10)

    ranking = bank.get_clients_ranking()[:3]
    print("\n[REPORT] Top-3 clients by total balance:")
    for place, (cid, total) in enumerate(ranking, start=1):
        print(f"  {place}. client={cid} total_balance={total:.2f}")

    print(f"\n[REPORT] Total bank balance (exclude closed): {bank.get_total_balance():.2f}")
    print_tx_stats(txs)
    print_suspicious(risk, min_level=RiskLevel.MEDIUM, limit=10)

    stats = audit.error_stats()
    print("\n[REPORT] Audit error stats (top):")
    for k, v in sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {k}: {v}")

    critical = audit.filter(min_level=AuditLevel.CRITICAL)
    print(f"\n[REPORT] CRITICAL audit events: {len(critical)}")

    if bank.suspicious_events:
        print(f"\n[REPORT] Bank suspicious events: {len(bank.suspicious_events)} (show up to 5)")
        for e in bank.suspicious_events[:5]:
            print(f"  - {e.timestamp.isoformat()} client={e.client_id} action={e.action} reason={e.reason}")

    bank_report = rb.build_bank_report(top_n=3)
    risk_report = rb.build_risk_report()
    client_report = rb.build_client_report(chosen_client)

    rb.export_to_json(bank_report, "bank_report.json")
    rb.export_to_json(risk_report, "risk_report.json")
    rb.export_to_json(client_report, f"client_{chosen_client}_report.json")

    rb.export_to_csv("bank", bank_report)
    rb.export_to_csv("risk", risk_report)
    rb.export_to_csv("client", client_report)

    rb.save_charts(bank_report=bank_report, risk_report=risk_report)
    print("\n[DAY7] Reports saved to: docs/reports/")


if __name__ == "__main__":
    main()
