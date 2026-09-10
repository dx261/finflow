"""Statement import endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import CurrentUser
from app.modules.statements.schemas import (
    ImportErrorRead,
    StatementImportDetail,
    StatementImportRead,
    UploadResult,
)
from app.modules.statements.service import StatementService

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/statements", tags=["statements"])


@router.post("/upload", response_model=UploadResult, status_code=202)
async def upload_statement(
    current_user: CurrentUser,
    session: DbSession,
    account_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    force_import: Annotated[bool, Query()] = False,
) -> UploadResult:
    """Stage a statement file. Parsing is processed asynchronously."""
    content = await file.read()
    filename = file.filename or "statement"
    return await StatementService(session).upload(
        user_id=current_user.id,
        account_id=account_id,
        filename=filename,
        content=content,
        force_import=force_import,
    )


@router.get("", response_model=list[StatementImportRead])
async def list_imports(
    current_user: CurrentUser,
    session: DbSession,
    account_id: uuid.UUID,
) -> list[StatementImportRead]:
    records = await StatementService(session).list_imports_for_user(current_user.id, account_id)
    return [StatementImportRead.model_validate(record) for record in records]


@router.get("/{import_id}", response_model=StatementImportDetail)
async def import_detail(
    current_user: CurrentUser,
    session: DbSession,
    import_id: uuid.UUID,
) -> StatementImportDetail:
    service = StatementService(session)
    record = await service.get_import_for_user(current_user.id, import_id)
    errors = await service.repository.list_errors(import_id)
    return StatementImportDetail(
        import_record=StatementImportRead.model_validate(record),
        errors=[ImportErrorRead.model_validate(error) for error in errors],
    )
