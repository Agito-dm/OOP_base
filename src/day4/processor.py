from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from src.day1.exceptions.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)
from src.day1.model.abstract_account import Currency
from src.day2.model.premium_account import PremiumAccount
from src.day3.bank import Bank
from src.day4.model.transaction import Transaction, TransactionStatus, TransactionType
from src.day4.queue import TransactionQueue


@dataclass
class ProcessingError:
    tx_id: str
    attempts: int
    error_type: str
    message: str
    timestamp: datetime


class TransactionProcessor:
    def __init__(
        self,
        bank: Bank,
        queue: TransactionQueue,
        *,
        time_provider: Optional[Callable[[], datetime]] = None,
        max_attempts: int = 3,
        external_fee_rate: float = 0.01,
        external_fee_fixed: float = 1.0,  # в валюте транзакции
    ) -> None:
        self.bank = bank
        self.queue = queue
        self._now = time_provider or datetime.now

        self.max_attempts = max_attempts
        self.external_fee_rate = float(external_fee_rate)
        self.external_fee_fixed = float(external_fee_fixed)

        self.error_log: List[ProcessingError] = []

        # простая таблица курсов к USD
        self._to_usd: Dict[Currency, float] = {
            Currency.USD: 1.0,
            Currency.EUR: 1.10,
            Currency.RUB: 1.0 / 90.0, # 1 RUB примерно 0.0111 USD
            Currency.KZT: 1.0 / 450.0,
            Currency.CNY: 1.0 / 7.2,
        }

    def convert(self, amount: float, from_cur: Currency, to_cur: Currency) -> float:
        if from_cur == to_cur:
            return float(amount)
        usd = float(amount) * self._to_usd[from_cur]
        return usd / self._to_usd[to_cur]

    def _calc_fee(self, tx: Transaction) -> float:
        if tx.tx_type == TransactionType.EXTERNAL_TRANSFER:
            return float(tx.amount) * self.external_fee_rate + self.external_fee_fixed
        return 0.0

    def _is_retryable(self, exc: Exception) -> bool:
        # frozen/closed/invalid можно повторить, например, админ разморозит, исправят ограничения
        return isinstance(exc, (AccountFrozenError, AccountClosedError, InvalidOperationError))

    def process_next(self) -> Optional[Transaction]:
        tx = self.queue.pop_next_ready()
        if tx is None:
            return None

        # если уже отменили, то возвращаем
        if tx.status == TransactionStatus.CANCELED:
            return tx

        tx.attempts += 1
        tx.status = TransactionStatus.PROCESSING
        tx.started_at = self._now()

        try:
            self._process(tx)
            tx.status = TransactionStatus.COMPLETED
            tx.finished_at = self._now()
            return tx

        except Exception as e:
            tx.decline_reason = f"{type(e).__name__}: {str(e)}"
            self.error_log.append(
                ProcessingError(
                    tx_id=tx.tx_id,
                    attempts=tx.attempts,
                    error_type=type(e).__name__,
                    message=str(e),
                    timestamp=self._now(),
                )
            )

            should_retry = self._is_retryable(e) and tx.attempts < self.max_attempts
            if should_retry:
                # повторение позже
                delay = timedelta(seconds=60 * tx.attempts)
                tx.status = TransactionStatus.QUEUED
                self.queue.add(tx, priority=tx.priority, run_at=self._now() + delay)
                return tx

            tx.status = TransactionStatus.FAILED
            tx.finished_at = self._now()
            return tx

    def process_all_ready(self, limit: int = 10_000) -> List[Transaction]:
        done: List[Transaction] = []
        for _ in range(limit):
            tx = self.process_next()
            if tx is None:
                break
            done.append(tx)
        return done

    def _process(self, tx: Transaction) -> None:
        # базовая валидация суммы
        try:
            amount = float(tx.amount)
        except (TypeError, ValueError):
            raise InvalidOperationError("Сумма транзакции должна быть числом.")
        if amount <= 0:
            raise InvalidOperationError("Сумма транзакции должна быть > 0.")

        sender = self.bank.accounts.get(tx.sender_account_id)
        if not sender:
            raise InvalidOperationError("Счет отправителя не найден.")

        # Правило запрет переводов при минусе (кроме премиум)
        if sender.get_account_info()["balance"] < 0 and not isinstance(sender, PremiumAccount):
            raise InvalidOperationError("Переводы запрещены при отрицательном балансе (кроме PremiumAccount).")

        # Правило запрет на замороженные, закрытые счета
        if sender.status != sender.status.__class__.ACTIVE:
            pass

        if sender.status.value == "frozen":
            raise AccountFrozenError("Счет отправителя заморожен.")
        if sender.status.value == "closed":
            raise AccountClosedError("Счет отправителя закрыт.")

        # получатель
        recipient = None
        if tx.tx_type == TransactionType.INTERNAL_TRANSFER:
            if not tx.recipient_account_id:
                raise InvalidOperationError("Для внутреннего перевода нужен recipient_account_id.")
            recipient = self.bank.accounts.get(tx.recipient_account_id)
            if not recipient:
                raise InvalidOperationError("Счет получателя не найден.")
            if recipient.status.value == "frozen":
                raise AccountFrozenError("Счет получателя заморожен.")
            if recipient.status.value == "closed":
                raise AccountClosedError("Счет получателя закрыт.")

        # комиссия в валюте транзакции
        tx.fee = self._calc_fee(tx)

        total_in_tx_currency = tx.amount + tx.fee

        # дебетуем отправителя в его валюте
        debit_amount_in_sender_cur = self.convert(total_in_tx_currency, tx.currency, sender.currency)
        sender.withdraw(debit_amount_in_sender_cur)

        # зачисление получателю, если внутренний перевод
        if recipient is not None:
            credit_amount_in_recipient_cur = self.convert(tx.amount, tx.currency, recipient.currency)
            recipient.deposit(credit_amount_in_recipient_cur)
