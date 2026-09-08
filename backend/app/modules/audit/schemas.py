"""Audit log schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    trace_id: str | None
    created_at: datetime
