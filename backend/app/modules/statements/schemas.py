"""Statement import schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.modules.statements.models import StatementImportStatus


class UploadResult(BaseModel):
    import_id: uuid.UUID
    status: StatementImportStatus
    is_duplicate: bool
    message: str


class StatementImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    original_filename: str
    file_type: str
    status: StatementImportStatus
    statement_start_date: date | None
    statement_end_date: date | None
    total_rows: int
    success_rows: int
    failed_rows: int
    created_at: datetime
    completed_at: datetime | None


class ImportErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_number: int | None
    field: str | None
    raw_value: str | None
    error_code: str
    message: str


class StatementImportDetail(BaseModel):
    import_record: StatementImportRead
    errors: list[ImportErrorRead]
