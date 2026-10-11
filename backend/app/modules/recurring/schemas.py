"""Recurring payment schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.payments.models import PaymentPriority
from app.modules.recurring.models import RecurringFrequency


class RecurringCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    frequency: RecurringFrequency
    day_of_month: int = Field(ge=1, le=31)
    start_date: date
    end_date: date | None = None
    preferred_account_id: uuid.UUID | None = None
    priority: PaymentPriority = PaymentPriority.NORMAL

    @model_validator(mode="after")
    def validate_dates(self) -> "RecurringCreate":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class RecurringUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    frequency: RecurringFrequency | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    start_date: date | None = None
    end_date: date | None = None
    preferred_account_id: uuid.UUID | None = None
    priority: PaymentPriority | None = None
    enabled: bool | None = None


class RecurringRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    amount: Decimal
    currency: str
    frequency: RecurringFrequency
    day_of_month: int
    start_date: date
    end_date: date | None
    preferred_account_id: uuid.UUID | None
    priority: PaymentPriority
    enabled: bool
    created_at: datetime
