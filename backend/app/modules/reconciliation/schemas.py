"""Reconciliation schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.reconciliation.models import ReconStatus


class ReconRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    transaction_id: uuid.UUID
    total_score: float
    amount_score: float
    account_score: float
    date_score: float
    counterparty_score: float
    reference_score: float
    status: ReconStatus
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime | None
    created_at: datetime


class SelectTransaction(BaseModel):
    transaction_id: uuid.UUID
