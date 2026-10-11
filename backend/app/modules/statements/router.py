"""Statement import endpoints."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.modules.auth.deps import DataOwnerId, OwnerUser
from app.modules.statements.models import StatementImportStatus
from app.modules.statements.schemas import (
    ImportErrorRead,
    StatementImportDetail,
    StatementImportRead,
    UploadResult,
)
from app.modules.statements.service import StatementService

logger = logging.getLogger("finflow")

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/statements", tags=["statements"])


def _dispatch_import(import_id: str) -> bool:
    """Enqueue the import task, degrading gracefully when enqueue fails."""
    if not settings.statement_import_async:
        return True
    try:
        from app.workers.tasks import process_import_task

        process_import_task.delay(import_id)
        return True
    except Exception:
        logger.warning("import_enqueue_failed", extra={"import_id": import_id}, exc_info=True)
        return False


async def _read_upload(file: UploadFile) -> bytes:
    """Read at most the configured limit instead of trusting Content-Length."""
    from app.core.exceptions import PayloadTooLargeError

    limit = settings.max_upload_size_mb * 1024 * 1024
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > limit:
            raise PayloadTooLargeError(
                f"Statement exceeds the {settings.max_upload_size_mb} MB upload limit."
            )
    return bytes(content)


@router.post("/upload", response_model=UploadResult, status_code=202)
async def upload_statement(
    owner: OwnerUser,
    session: DbSession,
    account_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    force_import: Annotated[bool, Query()] = False,
) -> UploadResult:
    """Stage a statement file. Parsing is processed asynchronously."""
    content = await _read_upload(file)
    filename = file.filename or "statement"
    result = await StatementService(session).upload(
        user_id=owner.id,
        account_id=account_id,
        filename=filename,
        content=content,
        force_import=force_import,
    )
    if not result.is_duplicate and settings.statement_import_async:
        service = StatementService(session)
        await service.mark_queued(result.import_id)
        result.status = StatementImportStatus.QUEUED
        if not _dispatch_import(str(result.import_id)):
            await service.mark_dispatch_failed(result.import_id)
            result.status = StatementImportStatus.FAILED
    elif not result.is_duplicate and settings.local_demo:
        # No Redis/Celery in the SQLite showcase: finish parsing before returning.
        record = await StatementService(session).process_import(result.import_id)
        result.status = record.status
        result.message = "Statement processed locally."
    return result


@router.get("", response_model=list[StatementImportRead])
async def list_imports(
    data_owner_id: DataOwnerId,
    session: DbSession,
    account_id: uuid.UUID,
) -> list[StatementImportRead]:
    records = await StatementService(session).list_imports_for_user(data_owner_id, account_id)
    return [StatementImportRead.model_validate(record) for record in records]


@router.get("/{import_id}", response_model=StatementImportDetail)
async def import_detail(
    data_owner_id: DataOwnerId,
    session: DbSession,
    import_id: uuid.UUID,
) -> StatementImportDetail:
    service = StatementService(session)
    record = await service.get_import_for_user(data_owner_id, import_id)
    errors = await service.repository.list_errors(import_id)
    return StatementImportDetail(
        import_record=StatementImportRead.model_validate(record),
        errors=[ImportErrorRead.model_validate(error) for error in errors],
    )
