"""Account planning balance tests (§13)."""

import uuid
from decimal import Decimal

from app.core.database import AsyncSessionLocal
from app.modules.allocation.models import AllocationStatus, FundAllocation


async def _create_account(
    client, auth_headers, bank_code="ICBC", balance="30000", minimum="10000"
) -> str:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == bank_code)
    response = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "bank_id": bank_id,
            "name": "测试账户",
            "actual_balance": balance,
            "minimum_balance": minimum,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_planning_available_without_allocations(client, seeded_banks, auth_headers) -> None:
    account_id = await _create_account(client, auth_headers)

    detail = await client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    body = detail.json()
    assert body["actual_balance"] == "30000.00"
    assert body["minimum_balance"] == "10000.00"
    assert body["reserved_amount"] == "0.00"
    assert body["planning_available"] == "20000.00"


async def test_reserved_allocations_reduce_planning_available(
    client, seeded_banks, auth_headers
) -> None:
    account_id = await _create_account(client, auth_headers)
    # A payment exists so allocations can reference it.
    payment = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "学费", "amount": "20000.00", "planned_date": "2026-10-01"},
    )
    payment_id = payment.json()["id"]

    # Insert one RESERVED and one PROPOSED allocation directly.
    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                FundAllocation(
                    payment_id=uuid.UUID(payment_id),
                    account_id=uuid.UUID(account_id),
                    allocated_amount=Decimal("5000.00"),
                    status=AllocationStatus.RESERVED,
                ),
                FundAllocation(
                    payment_id=uuid.UUID(payment_id),
                    account_id=uuid.UUID(account_id),
                    allocated_amount=Decimal("3000.00"),
                    status=AllocationStatus.PROPOSED,
                ),
            ]
        )
        await session.commit()

    detail = await client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    body = detail.json()
    # Only RESERVED allocations count as virtual reservations.
    assert body["reserved_amount"] == "5000.00"
    assert body["planning_available"] == "15000.00"


async def test_multiple_reserved_allocations_sum(client, seeded_banks, auth_headers) -> None:
    account_id = await _create_account(client, auth_headers)
    payment = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "多笔", "amount": "30000.00", "planned_date": "2026-10-01"},
    )
    payment_id = payment.json()["id"]

    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                FundAllocation(
                    payment_id=uuid.UUID(payment_id),
                    account_id=uuid.UUID(account_id),
                    allocated_amount=Decimal("2000.00"),
                    status=AllocationStatus.RESERVED,
                ),
                FundAllocation(
                    payment_id=uuid.UUID(payment_id),
                    account_id=uuid.UUID(account_id),
                    allocated_amount=Decimal("3000.00"),
                    status=AllocationStatus.RESERVED,
                ),
            ]
        )
        await session.commit()

    detail = await client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert detail.json()["reserved_amount"] == "5000.00"
    assert detail.json()["planning_available"] == "15000.00"
