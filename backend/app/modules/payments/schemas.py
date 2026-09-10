"""Payment plan schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.models import PaymentPriority, PaymentStatus


class PaymentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    payee_name: str | None = Field(default=None, max_length=255)
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    planned_date: date
    priority: PaymentPriority = PaymentPriority.NORMAL
    preferred_account_id: uuid.UUID | None = None


class PaymentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    payee_name: str | None = Field(default=None, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    planned_date: date | None = None
    priority: PaymentPriority | None = None
    preferred_account_id: uuid.UUID | None = None


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    payee_name: str | None
    amount: Decimal
    currency: str
    planned_date: date
    priority: PaymentPriority
    preferred_account_id: uuid.UUID | None
    status: PaymentStatus
    manual_execution_at: datetime | None
    manual_execution_account_id: uuid.UUID | None
    manual_execution_note: str | None
    bank_reference: str | None
    created_at: datetime
    updated_at: datetime
