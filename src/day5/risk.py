from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from src.day1.model.abstract_account import Currency
from src.day3.bank import Bank
from src.day4.model.transaction import Transaction, TransactionType


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RiskFinding:
    code: str
    description: str
    score: int


@dataclass
class RiskRecord:
    timestamp: datetime
    client_id: str
    tx_id: str
    risk_level: RiskLevel
    findings: list[RiskFinding]


class RiskAnalyzer:
    """
    Определение подозрительных операций:
    - крупная сумма
    - частые операции
    - переводы на новые счета
    - операции ночью
    """

    def __init__(
        self,
        *,
        time_provider: Optional[Callable[[], datetime]] = None,
        large_amount_usd: float = 2000.0,
        frequent_window_minutes: int = 10,
        frequent_threshold: int = 5,
    ) -> None:
        self._now = time_provider or datetime.now

        self.large_amount_usd = float(large_amount_usd)
        self.frequent_window = timedelta(minutes=int(frequent_window_minutes))
        self.frequent_threshold = int(frequent_threshold)

        self.history: list[RiskRecord] = []
        self._seen_recipients: dict[str, set[str]] = {}  # client_id -> set(recipient_account_id)

        self._to_usd = {
            Currency.USD: 1.0,
            Currency.EUR: 1.10,
            Currency.RUB: 1.0 / 90.0,
            Currency.KZT: 1.0 / 450.0,
            Currency.CNY: 1.0 / 7.2,
        }

    def _is_night(self, dt: datetime) -> bool:
        t = dt.time()
        return time(0, 0) <= t < time(5, 0)

    def _to_usd_amount(self, amount: float, cur: Currency) -> float:
        return float(amount) * self._to_usd[cur]

    def _recent_ops_count(self, client_id: str) -> int:
        now = self._now()
        start = now - self.frequent_window
        return sum(1 for r in self.history if r.client_id == client_id and r.timestamp >= start)

    def evaluate(self, bank: Bank, tx: Transaction) -> RiskRecord:
        now = self._now()

        client_id = bank._account_owner.get(tx.sender_account_id)
        if not client_id:
            client_id = "unknown"

        findings: list[RiskFinding] = []
        score = 0

        # Крупная сумма
        amount_usd = self._to_usd_amount(tx.amount, tx.currency)
        if amount_usd >= self.large_amount_usd:
            findings.append(RiskFinding("LARGE_AMOUNT", f"Large amount: ~{amount_usd:.2f} USD", 2))
            score += 2

        # Частые операции
        recent = self._recent_ops_count(client_id)
        if recent >= self.frequent_threshold:
            findings.append(RiskFinding("FREQUENT_OPS", f"Frequent ops: {recent} in window", 2))
            score += 2

        # Перевод на новый счет (только для внутренних переводов)
        if tx.tx_type == TransactionType.INTERNAL_TRANSFER and tx.recipient_account_id:
            seen = self._seen_recipients.setdefault(client_id, set())
            if tx.recipient_account_id not in seen:
                findings.append(RiskFinding("NEW_RECIPIENT", "Transfer to new recipient account", 1))
                score += 1

        # Ночь
        if self._is_night(now):
            findings.append(RiskFinding("NIGHT_OP", "Operation during night hours (00:00-05:00)", 1))
            score += 1

        # уровни риска
        if score >= 3:
            risk = RiskLevel.HIGH
        elif score == 2:
            risk = RiskLevel.MEDIUM
        elif score == 1:
            risk = RiskLevel.LOW
        else:
            risk = RiskLevel.LOW

        record = RiskRecord(timestamp=now, client_id=client_id, tx_id=tx.tx_id, risk_level=risk, findings=findings)
        return record

    def commit(self, tx: Transaction, record: RiskRecord) -> None:
        """
        Вызываем после оценки, чтобы:
        - сохранить историю
        - запомнить получателя (если internal)
        """
        self.history.append(record)

        if tx.tx_type == TransactionType.INTERNAL_TRANSFER and tx.recipient_account_id:
            seen = self._seen_recipients.setdefault(record.client_id, set())
            seen.add(tx.recipient_account_id)

    def suspicious_operations(self, min_level: RiskLevel = RiskLevel.MEDIUM) -> list[RiskRecord]:
        rank = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        return [r for r in self.history if rank[r.risk_level] >= rank[min_level]]

    def client_risk_profile(self, client_id: str) -> dict[str, Any]:
        levels = [r.risk_level for r in self.history if r.client_id == client_id]
        counts = {"low": 0, "medium": 0, "high": 0}
        for lv in levels:
            counts[lv.value] += 1
        max_level = "low"
        if counts["high"] > 0:
            max_level = "high"
        elif counts["medium"] > 0:
            max_level = "medium"
        return {"client_id": client_id, "counts": counts, "max_risk": max_level}
