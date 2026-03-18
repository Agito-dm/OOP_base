from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from src.day1.model.abstract_account import Currency


class TransactionType(Enum):
    INTERNAL_TRANSFER = "internal_transfer"
    EXTERNAL_TRANSFER = "external_transfer"


class TransactionStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class Transaction:
    tx_type: TransactionType
    amount: float
    currency: Currency

    sender_account_id: str
    recipient_account_id: Optional[str] = None  # None для внешнего перевода

    priority: int = 0
    scheduled_for: Optional[datetime] = None

    fee: float = 0.0
    status: TransactionStatus = TransactionStatus.PENDING
    decline_reason: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    attempts: int = 0
    tx_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
