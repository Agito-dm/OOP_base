from __future__ import annotations

import heapq
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from src.day4.model.transaction import Transaction, TransactionStatus


@dataclass(frozen=True)
class _QueueItem:
    run_at: datetime
    neg_priority: int
    seq: int
    tx_id: str


class TransactionQueue:
    def __init__(self, time_provider: Optional[Callable[[], datetime]] = None) -> None:
        self._now = time_provider or datetime.now
        self._heap: List[Tuple] = []
        self._seq = 0
        self._tx: Dict[str, Transaction] = {}

    def add(self, tx: Transaction, *, priority: int = 0, run_at: Optional[datetime] = None) -> str:
        if run_at is None:
            run_at = self._now()

        tx.priority = int(priority)
        tx.scheduled_for = run_at
        tx.status = TransactionStatus.QUEUED

        self._tx[tx.tx_id] = tx
        item = _QueueItem(run_at=run_at, neg_priority=-tx.priority, seq=self._seq, tx_id=tx.tx_id)
        self._seq += 1

        heapq.heappush(self._heap, (item.run_at, item.neg_priority, item.seq, item.tx_id))
        return tx.tx_id

    def cancel(self, tx_id: str, reason: str = "canceled") -> None:
        tx = self._tx.get(tx_id)
        if not tx:
            return
        if tx.status in (TransactionStatus.COMPLETED, TransactionStatus.FAILED):
            return
        tx.status = TransactionStatus.CANCELED
        tx.decline_reason = reason
        tx.finished_at = self._now()

    def get(self, tx_id: str) -> Optional[Transaction]:
        return self._tx.get(tx_id)

    def pop_next_ready(self) -> Optional[Transaction]:
        """
        Возвращает следующую готовую транзакцию с учетом:
        - run_at (отложенные)
        - priority (больше = раньше)
        - отмененные пропускаем
        """
        now = self._now()

        while self._heap:
            run_at, neg_pr, seq, tx_id = heapq.heappop(self._heap)
            tx = self._tx.get(tx_id)
            if not tx:
                continue

            if tx.status == TransactionStatus.CANCELED:
                continue

            if run_at > now:
                # еще рано, кладется обратно и выход
                heapq.heappush(self._heap, (run_at, neg_pr, seq, tx_id))
                return None

            return tx

        return None

    def __len__(self) -> int:
        return len(self._tx)
