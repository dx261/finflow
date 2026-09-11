"""Forecast schemas."""

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.forecast.models import CashFlowPlanStatus, CashFlowPlanType


class CashFlowPlanCreate(BaseModel):
    type: CashFlowPlanType
    name: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0)
    date: date_type
    account_id: uuid.UUID | None = None
    is_recurring: bool = False


class CashFlowPlanUpdate(BaseModel):
    type: CashFlowPlanType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    amount: Decimal | None = Field(default=None, gt=0)
    date: date_type | None = None
    account_id: uuid.UUID | None = None
    status: CashFlowPlanStatus | None = None


class CashFlowPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: CashFlowPlanType
    name: str
    amount: Decimal
    date: date_type
    account_id: uuid.UUID | None
    status: CashFlowPlanStatus
    is_recurring: bool
    created_at: datetime


class ForecastDayRead(BaseModel):
    date: date_type
    starting_balance: Decimal
    expected_income: Decimal
    expected_expense: Decimal
    ending_balance: Decimal
    below_minimum: bool


class ForecastResponse(BaseModel):
    accounts: dict[str, list[ForecastDayRead]]
    aggregate: list[ForecastDayRead]
    warnings: list[dict]
