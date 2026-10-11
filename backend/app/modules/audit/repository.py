"""Audit log data access."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        before_data: dict[str, Any] | None,
        after_data: dict[str, Any] | None,
        trace_id: str | None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_data=before_data,
            after_data=after_data,
            trace_id=trace_id,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list(
        self,
        *,
        user_id: uuid.UUID,
        resource_type: str | None,
        resource_id: str | None,
        action: str | None,
        limit: int,
        offset: int,
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at.desc())
        )
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id is not None:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        return list(result)
