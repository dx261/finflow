"""Fund allocation data access."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.allocation.models import AllocationStatus, FundAllocation


class AllocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_payment(self, payment_id: uuid.UUID) -> list[FundAllocation]:
        result = await self.session.scalars(
            select(FundAllocation)
            .where(FundAllocation.payment_id == payment_id)
            .order_by(FundAllocation.created_at)
        )
        return list(result)

    async def delete_proposed(self, payment_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(FundAllocation).where(
                FundAllocation.payment_id == payment_id,
                FundAllocation.status == AllocationStatus.PROPOSED,
            )
        )
