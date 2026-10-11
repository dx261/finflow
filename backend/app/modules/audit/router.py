"""Read-only audit log endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.audit.schemas import AuditLogRead
from app.modules.audit.service import AuditService
from app.modules.auth.deps import DataOwnerId

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    data_owner_id: DataOwnerId,
    session: DbSession,
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogRead]:
    logs = await AuditService(session).list_logs(
        user_id=data_owner_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return [AuditLogRead.model_validate(log) for log in logs]
