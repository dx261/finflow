"""Bank schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BankCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    country: str = Field(default="CN", max_length=2)
    logo: str | None = Field(default=None, max_length=255)
    statement_parser_type: str = Field(default="GENERIC", max_length=30)


class BankUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=2)
    logo: str | None = Field(default=None, max_length=255)
    statement_parser_type: str | None = Field(default=None, max_length=30)


class BankRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    country: str
    logo: str | None
    statement_parser_type: str
    created_at: datetime
