"""Account schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.accounts.models import AccountStatus, AccountType, BalanceSource


class AccountCreate(BaseModel):
    bank_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    masked_account_no: str | None = Field(default=None, max_length=50)
    account_type: AccountType = AccountType.CHECKING
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    actual_balance: Decimal = Decimal("0")
    balance_as_of: datetime | None = None
    minimum_balance: Decimal = Decimal("0")
    include_in_allocation: bool = True


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    masked_account_no: str | None = Field(default=None, max_length=50)
    account_type: AccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    actual_balance: Decimal | None = None
    balance_as_of: datetime | None = None
    minimum_balance: Decimal | None = None
    include_in_allocation: bool | None = None
    status: AccountStatus | None = None


class AccountRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    bank_id: uuid.UUID
    name: str
    masked_account_no: str | None
    account_type: AccountType
    currency: str
    actual_balance: Decimal
    balance_as_of: datetime | None
    minimum_balance: Decimal
    include_in_allocation: bool
    status: AccountStatus
    # Derived balances — never persisted.
    reserved_amount: Decimal
    planning_available: Decimal
    created_at: datetime
    updated_at: datetime


class BalanceSnapshotCreate(BaseModel):
    snapshot_date: date | None = None
    source: BalanceSource = BalanceSource.MANUAL


class BalanceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    balance: Decimal
    available_balance: Decimal
    snapshot_date: date
    source: BalanceSource
    created_at: datetime
