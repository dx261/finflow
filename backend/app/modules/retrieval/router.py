"""Transaction search endpoints."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import CurrentUser
from app.modules.retrieval.service import RetrievalService, TransactionSearch
from app.modules.statements.models import TransactionDirection

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    transaction_date: date | None
    direction: TransactionDirection
    amount: Decimal
    currency: str
    counterparty_name: str | None
    description: str
    transaction_type: str
    external_reference: str | None


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    current_user: CurrentUser,
    session: DbSession,
    account_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    category: str | None = None,
    keyword: str | None = None,
    direction: TransactionDirection | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TransactionRead]:
    """Search historical transactions across the user's accounts."""
    search = TransactionSearch(
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        category=category,
        keyword=keyword,
        direction=direction,
    )
    transactions = await RetrievalService(session).list_transactions(current_user.id, search, limit)
    return [TransactionRead.model_validate(t) for t in transactions]
