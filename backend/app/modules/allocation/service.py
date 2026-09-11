"""Allocation helpers.

For TASK-026 the key derivation is the virtual reserved amount: the sum of
``RESERVED`` allocations against an account, which feeds the planning
balance ``actual - reserved - minimum``.
"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.allocation.models import AllocationStatus, FundAllocation


async def sum_reserved_amount(session: AsyncSession, account_id: uuid.UUID) -> Decimal:
    """Sum of currently reserved allocations for an account."""
    result = await session.scalar(
        select(func.coalesce(func.sum(FundAllocation.allocated_amount), 0)).where(
            FundAllocation.account_id == account_id,
            FundAllocation.status == AllocationStatus.RESERVED,
        )
    )
    return Decimal(str(result or 0))
