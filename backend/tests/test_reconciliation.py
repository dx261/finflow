"""Reconciliation integration tests (§98 golden path)."""

import uuid
from datetime import date
from decimal import Decimal

from app.core.database import AsyncSessionLocal
from app.modules.statements.models import StatementImport, Transaction


async def _create_account(client, auth_headers, bank_code="ICBC", balance="20000") -> str:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == bank_code)
    response = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"bank_id": bank_id, "name": "账户", "actual_balance": balance},
    )
    return response.json()["id"]


async def _reserved_executed_payment(
    client, auth_headers, account_id, amount: str = "8000.00"
) -> str:
    payment = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "房租", "payee_name": "房东", "amount": amount, "planned_date": "2026-09-05"},
    )
    payment_id = payment.json()["id"]
    await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "PLANNED"},
    )
    await client.post(f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers)
    await client.post(f"/api/v1/payments/{payment_id}/allocations/confirm", headers=auth_headers)
    executed = await client.post(
        f"/api/v1/payments/{payment_id}/manual-execution",
        headers=auth_headers,
        json={"account_id": account_id},
    )
    assert executed.status_code == 200, executed.text
    return payment_id


async def _insert_txn(
    account_id: str,
    amount: Decimal,
    *,
    txn_date: date = date(2026, 9, 5),
    counterparty: str = "房东",
    direction: str = "DEBIT",
) -> str:
    async with AsyncSessionLocal() as session:
        statement_import = StatementImport(
            account_id=uuid.UUID(account_id),
            original_filename="test.xlsx",
            stored_filename="test.xlsx",
            file_hash="abc",
            file_type="xlsx",
            status="SUCCESS",
            total_rows=1,
            success_rows=1,
            failed_rows=0,
        )
        session.add(statement_import)
        await session.flush()
        txn = Transaction(
            account_id=uuid.UUID(account_id),
            statement_import_id=statement_import.id,
            transaction_date=txn_date,
            direction=direction,
            amount=amount,
            currency="CNY",
            counterparty_name=counterparty,
            description="房租",
            fingerprint=f"fp-{direction}-{amount}-{txn_date}-{counterparty}",
        )
        session.add(txn)
        await session.commit()
        return str(txn.id)


async def test_golden_path_auto_match_and_settle(client, seeded_banks, auth_headers) -> None:
    account_id = await _create_account(client, auth_headers)
    payment_id = await _reserved_executed_payment(client, auth_headers, account_id)
    await _insert_txn(account_id, Decimal("8000.00"))

    recon = await client.post(f"/api/v1/payments/{payment_id}/reconcile", headers=auth_headers)
    assert recon.status_code == 200, recon.text
    body = recon.json()
    assert body["status"] == "AUTO_MATCHED"
    assert body["total_score"] >= 0.80

    pending = await client.get("/api/v1/reconciliations/pending", headers=auth_headers)
    assert [item["id"] for item in pending.json()] == [body["id"]]

    transaction = await client.get(
        f"/api/v1/transactions/{body['transaction_id']}", headers=auth_headers
    )
    assert transaction.status_code == 200
    assert transaction.json()["amount"] == "8000.00"

    confirmed = await client.post(
        f"/api/v1/reconciliations/{body['id']}/confirm", headers=auth_headers
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"

    payment = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
    assert payment.json()["status"] == "SETTLED"

    # Allocations settled too.
    allocations = await client.get(
        f"/api/v1/payments/{payment_id}/allocations", headers=auth_headers
    )
    assert all(a["status"] == "SETTLED" for a in allocations.json())


async def test_low_score_goes_to_review(client, seeded_banks, auth_headers) -> None:
    account_id = await _create_account(client, auth_headers)
    payment_id = await _reserved_executed_payment(client, auth_headers, account_id)
    # Exact amount but weaker date/counterparty signals -> manual review.
    await _insert_txn(
        account_id,
        Decimal("8000.00"),
        txn_date=date(2026, 9, 10),
        counterparty="完全不同商户",
    )

    recon = await client.post(f"/api/v1/payments/{payment_id}/reconcile", headers=auth_headers)
    assert recon.status_code == 200, recon.text
    assert recon.json()["status"] == "REVIEW_REQUIRED"

    pending = await client.get("/api/v1/reconciliations/pending", headers=auth_headers)
    assert len(pending.json()) == 1


async def test_reject_does_not_settle(client, seeded_banks, auth_headers) -> None:
    account_id = await _create_account(client, auth_headers)
    payment_id = await _reserved_executed_payment(client, auth_headers, account_id)
    await _insert_txn(
        account_id,
        Decimal("8000.00"),
        txn_date=date(2026, 9, 10),
        counterparty="完全不同商户",
    )
    recon = await client.post(f"/api/v1/payments/{payment_id}/reconcile", headers=auth_headers)
    recon_id = recon.json()["id"]

    rejected = await client.post(f"/api/v1/reconciliations/{recon_id}/reject", headers=auth_headers)
    assert rejected.json()["status"] == "REJECTED"

    payment = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
    assert payment.json()["status"] == "RECONCILING"


async def test_release_reservations_back_to_planned(client, seeded_banks, auth_headers) -> None:
    # The release path is exercised from RESERVED via a fresh payment.
    await _create_account(client, auth_headers)
    payment = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "测试", "amount": "1000.00", "planned_date": "2026-10-01"},
    )
    fresh_id = payment.json()["id"]
    await client.post(
        f"/api/v1/payments/{fresh_id}/transition",
        headers=auth_headers,
        json={"target_status": "PLANNED"},
    )
    await client.post(f"/api/v1/payments/{fresh_id}/allocations/preview", headers=auth_headers)
    await client.post(f"/api/v1/payments/{fresh_id}/allocations/confirm", headers=auth_headers)

    released = await client.post(
        f"/api/v1/payments/{fresh_id}/release",
        headers=auth_headers,
        params={"target": "PLANNED"},
    )
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "PLANNED"

    allocations = await client.get(f"/api/v1/payments/{fresh_id}/allocations", headers=auth_headers)
    assert all(a["status"] == "RELEASED" for a in allocations.json())


async def test_select_transaction_rebinds_match(client, seeded_banks, auth_headers) -> None:
    account_id = await _create_account(client, auth_headers)
    payment_id = await _reserved_executed_payment(client, auth_headers, account_id)
    # Only the wrong transaction exists at reconcile time.
    await _insert_txn(
        account_id,
        Decimal("8000.00"),
        txn_date=date(2026, 9, 10),
        counterparty="完全不同商户",
    )

    recon = await client.post(f"/api/v1/payments/{payment_id}/reconcile", headers=auth_headers)
    assert recon.json()["status"] == "REVIEW_REQUIRED"

    # The correct transaction arrives later; the user rebinds the match.
    right_txn = await _insert_txn(account_id, Decimal("8000.00"))
    rebound = await client.post(
        f"/api/v1/reconciliations/{recon.json()['id']}/select-transaction",
        headers=auth_headers,
        json={"transaction_id": right_txn},
    )
    assert rebound.status_code == 200, rebound.text
    assert rebound.json()["transaction_id"] == right_txn
    assert rebound.json()["status"] == "AUTO_MATCHED"


async def test_confirm_marks_transaction_matched_and_prevents_reuse(
    client, seeded_banks, auth_headers
) -> None:
    account_id = await _create_account(client, auth_headers)
    first_payment = await _reserved_executed_payment(client, auth_headers, account_id)
    transaction_id = await _insert_txn(account_id, Decimal("8000.00"))

    recon = await client.post(f"/api/v1/payments/{first_payment}/reconcile", headers=auth_headers)
    confirmed = await client.post(
        f"/api/v1/reconciliations/{recon.json()['id']}/confirm", headers=auth_headers
    )
    assert confirmed.status_code == 200

    async with AsyncSessionLocal() as session:
        transaction = await session.get(Transaction, uuid.UUID(transaction_id))
        assert transaction is not None
        assert transaction.reconciliation_status == "MATCHED"

    second_payment = await _reserved_executed_payment(client, auth_headers, account_id)
    second = await client.post(f"/api/v1/payments/{second_payment}/reconcile", headers=auth_headers)
    assert second.status_code == 409
