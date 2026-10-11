"""Allocation schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.allocation.models import AllocationStatus


class AllocationItem(BaseModel):
    account_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class AllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    account_id: uuid.UUID
    allocated_amount: Decimal
    status: AllocationStatus
    algorithm_version: str
    created_at: datetime
