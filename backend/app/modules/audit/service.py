"""Audit log business logic."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.middleware import trace_id_var
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditLogRepository


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AuditLogRepository(session)

    async def record(
        self,
        *,
        user_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Append an audit entry.

        Does not commit — the caller commits within its own transaction so
        the audit entry is atomic with the operation it describes.
        """
        return await self.repository.create(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_data=before_data,
            after_data=after_data,
            trace_id=trace_id_var.get() or None,
        )

    async def list_logs(
        self,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        return await self.repository.list(
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            limit=limit,
            offset=offset,
        )
