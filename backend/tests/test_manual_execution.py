"""Manual execution confirmation tests (§29)."""

import uuid
from decimal import Decimal

from app.core.database import AsyncSessionLocal
from app.modules.allocation.models import AllocationStatus, FundAllocation
from app.modules.payments.models import PaymentPlan, PaymentStatus


async def _create_reserved_payment(client, seeded_banks, auth_headers) -> tuple[str, str]:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == "ICBC")
    account = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"bank_id": bank_id, "name": "账户", "actual_balance": "10000"},
    )
    account_id = account.json()["id"]

    payment = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "房租", "amount": "8000.00", "planned_date": "2026-10-01"},
    )
    payment_id = payment.json()["id"]

    async with AsyncSessionLocal() as session:
        record = await session.get(PaymentPlan, uuid.UUID(payment_id))
        record.status = PaymentStatus.RESERVED
        session.add(
            FundAllocation(
                payment_id=uuid.UUID(payment_id),
                account_id=uuid.UUID(account_id),
                allocated_amount=Decimal("8000.00"),
                status=AllocationStatus.RESERVED,
            )
        )
        await session.commit()

    return payment_id, account_id


async def test_manual_execution_records_details(client, seeded_banks, auth_headers) -> None:
    payment_id, account_id = await _create_reserved_payment(client, seeded_banks, auth_headers)

    response = await client.post(
        f"/api/v1/payments/{payment_id}/manual-execution",
        headers=auth_headers,
        json={
            "account_id": account_id,
            "note": "已通过手机银行完成转账",
            "bank_reference": "REF-2026-0901",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "MANUALLY_EXECUTED"
    assert body["bank_reference"] == "REF-2026-0901"
    assert body["manual_execution_note"] == "已通过手机银行完成转账"
    assert body["manual_execution_account_id"] == account_id
    assert body["manual_execution_at"] is not None


async def test_manual_execution_requires_reserved_or_waiting(
    client, seeded_banks, auth_headers
) -> None:
    payment = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "测试", "amount": "1000.00", "planned_date": "2026-10-01"},
    )
    payment_id = payment.json()["id"]

    response = await client.post(
        f"/api/v1/payments/{payment_id}/manual-execution", headers=auth_headers, json={}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_manual_execution_from_waiting_state(client, seeded_banks, auth_headers) -> None:
    payment_id, _ = await _create_reserved_payment(client, seeded_banks, auth_headers)
    await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "WAITING_MANUAL_EXECUTION"},
    )

    response = await client.post(
        f"/api/v1/payments/{payment_id}/manual-execution",
        headers=auth_headers,
        json={"note": "执行"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "MANUALLY_EXECUTED"


async def test_manual_execution_not_settled(client, seeded_banks, auth_headers) -> None:
    # The claim records MANUALLY_EXECUTED, never SETTLED.
    payment_id, _ = await _create_reserved_payment(client, seeded_banks, auth_headers)
    response = await client.post(
        f"/api/v1/payments/{payment_id}/manual-execution", headers=auth_headers, json={}
    )
    assert response.json()["status"] == "MANUALLY_EXECUTED"
