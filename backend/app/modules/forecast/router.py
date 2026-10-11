"""Forecast endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import DataOwnerId, OwnerUser
from app.modules.forecast.schemas import (
    CashFlowPlanCreate,
    CashFlowPlanRead,
    CashFlowPlanUpdate,
    ForecastResponse,
)
from app.modules.forecast.service import ForecastService

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(tags=["forecast"])


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    data_owner_id: DataOwnerId,
    session: DbSession,
    days: int = Query(default=30, ge=1, le=90),
) -> ForecastResponse:
    """Project balances 7/30/90 days out, with low-balance warnings."""
    return await ForecastService(session).forecast(data_owner_id, days)


@router.get("/cashflow-plans", response_model=list[CashFlowPlanRead])
async def list_plans(data_owner_id: DataOwnerId, session: DbSession) -> list[CashFlowPlanRead]:
    plans = await ForecastService(session).list_plans(data_owner_id)
    return [CashFlowPlanRead.model_validate(p) for p in plans]


@router.post("/cashflow-plans", response_model=CashFlowPlanRead, status_code=201)
async def create_plan(
    payload: CashFlowPlanCreate, owner: OwnerUser, session: DbSession
) -> CashFlowPlanRead:
    plan = await ForecastService(session).create_plan(owner.id, payload)
    return CashFlowPlanRead.model_validate(plan)


@router.put("/cashflow-plans/{plan_id}", response_model=CashFlowPlanRead)
async def update_plan(
    plan_id: uuid.UUID,
    payload: CashFlowPlanUpdate,
    owner: OwnerUser,
    session: DbSession,
) -> CashFlowPlanRead:
    plan = await ForecastService(session).update_plan(owner.id, plan_id, payload)
    return CashFlowPlanRead.model_validate(plan)


@router.delete("/cashflow-plans/{plan_id}", status_code=204)
async def delete_plan(plan_id: uuid.UUID, owner: OwnerUser, session: DbSession) -> None:
    await ForecastService(session).delete_plan(owner.id, plan_id)
