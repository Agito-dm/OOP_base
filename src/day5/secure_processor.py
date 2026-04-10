from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

from src.day1.exceptions.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)
from src.day4.model.transaction import Transaction, TransactionStatus
from src.day4.processor import TransactionProcessor
from src.day5.audit import AuditLog, AuditLevel
from src.day5.exceptions import HighRiskOperationError
from src.day5.risk import RiskAnalyzer, RiskLevel


class SecureTransactionProcessor(TransactionProcessor):
    """
    Расширение TransactionProcessor:
    - логирование (AuditLog)
    - риск-анализ (RiskAnalyzer)
    - блокировка high-risk операций
    """

    def __init__(
        self,
        *args,
        audit_log: AuditLog,
        risk_analyzer: RiskAnalyzer,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.audit = audit_log
        self.risk = risk_analyzer

    def _is_retryable(self, exc: Exception) -> bool:
        # не повторяем
        if isinstance(exc, HighRiskOperationError):
            return False
        return super()._is_retryable(exc)

    def process_next(self) -> Transaction | None:
        tx = self.queue.pop_next_ready()
        if tx is None:
            return None

        if tx.status == TransactionStatus.CANCELED:
            self.audit.log(AuditLevel.INFO, "Transaction canceled", tx_id=tx.tx_id)
            return tx

        tx.attempts += 1
        tx.status = TransactionStatus.PROCESSING
        tx.started_at = self._now()

        client_id = self.bank._account_owner.get(tx.sender_account_id)

        self.audit.log(AuditLevel.INFO, "Transaction processing started", client_id=client_id, tx_id=tx.tx_id)

        try:
            record = self.risk.evaluate(self.bank, tx)

            if record.risk_level == RiskLevel.HIGH:
                self.audit.log(
                    AuditLevel.CRITICAL,
                    "High risk transaction blocked",
                    client_id=record.client_id,
                    tx_id=tx.tx_id,
                    meta={"findings": [f.code for f in record.findings]},
                )
                self.risk.commit(tx, record)
                raise HighRiskOperationError("High risk operation blocked by bank policy.")

            if record.risk_level == RiskLevel.MEDIUM:
                self.audit.log(
                    AuditLevel.WARNING,
                    "Medium risk transaction detected",
                    client_id=record.client_id,
                    tx_id=tx.tx_id,
                    meta={"findings": [f.code for f in record.findings]},
                )

            # выполнение логики Day4
            self._process(tx)

            # фиксация риск-историю после успешного выполнения
            self.risk.commit(tx, record)

            tx.status = TransactionStatus.COMPLETED
            tx.finished_at = self._now()
            self.audit.log(AuditLevel.INFO, "Transaction completed", client_id=record.client_id, tx_id=tx.tx_id)
            return tx

        except Exception as e:
            tx.decline_reason = f"{type(e).__name__}: {str(e)}"

            self.audit.log(
                AuditLevel.ERROR,
                f"{type(e).__name__}: {str(e)}",
                client_id=client_id,
                tx_id=tx.tx_id,
            )

            # ретраи как в Day4
            should_retry = self._is_retryable(e) and tx.attempts < self.max_attempts
            if should_retry:
                delay = timedelta(seconds=60 * tx.attempts)
                tx.status = TransactionStatus.QUEUED
                self.queue.add(tx, priority=tx.priority, run_at=self._now() + delay)
                return tx

            tx.status = TransactionStatus.FAILED
            tx.finished_at = self._now()
            return tx
