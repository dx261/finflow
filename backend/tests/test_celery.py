"""Celery worker wiring tests."""

import io

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.workers.tasks import _run_process_import, process_import_task
from openpyxl import Workbook


def _xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["交易日期", "摘要", "借方金额", "贷方金额", "余额"])
    ws.append(["2026-09-01", "工资", None, 8000.0, 50000.0])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_celery_broker_uses_settings() -> None:
    assert celery_app.conf.broker_url == settings.redis_url
    assert celery_app.conf.result_backend == settings.redis_url


def test_process_import_task_registered() -> None:
    assert process_import_task.name == "statements.process_import"


async def test_process_import_task_core(
    client, seeded_banks, seeded_categories, auth_headers
) -> None:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == "ICBC")
    account = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"bank_id": bank_id, "name": "celery-account"},
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]

    upload = await client.post(
        "/api/v1/statements/upload",
        headers=auth_headers,
        data={"account_id": account_id},
        files={
            "file": (
                "statement.xlsx",
                _xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 202, upload.text
    import_id = upload.json()["import_id"]

    result = await _run_process_import(import_id)
    assert result["import_id"] == import_id
    assert result["status"] == "SUCCESS"
    assert result["success_rows"] == 1
    assert result["failed_rows"] == 0
