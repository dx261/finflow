"""Allocation API tests: preview, manual override, reservation."""


async def _create_account(
    client, auth_headers, bank_code, balance: str, minimum: str = "0", name: str = "账户"
) -> str:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == bank_code)
    response = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "bank_id": bank_id,
            "name": name,
            "actual_balance": balance,
            "minimum_balance": minimum,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _planned_payment(client, auth_headers, amount: str) -> str:
    created = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "学费", "amount": amount, "planned_date": "2026-10-01"},
    )
    payment_id = created.json()["id"]
    await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "PLANNED"},
    )
    return payment_id


async def test_preview_creates_proposed_and_allocated(client, seeded_banks, auth_headers) -> None:
    cmb = await _create_account(client, auth_headers, "CMB", "8000")
    icbc = await _create_account(client, auth_headers, "ICBC", "20000")
    payment_id = await _planned_payment(client, auth_headers, "10000")

    response = await client.post(
        f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    allocations = response.json()
    assert len(allocations) == 2
    assert all(a["status"] == "PROPOSED" for a in allocations)
    by_account = {a["account_id"]: a["allocated_amount"] for a in allocations}
    assert by_account[cmb] == "8000.00"  # CMB 8000 available drains fully first
    assert by_account[icbc] == "2000.00"

    payment = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
    assert payment.json()["status"] == "ALLOCATED"


async def test_confirm_reserves_and_updates_payment(client, seeded_banks, auth_headers) -> None:
    await _create_account(client, auth_headers, "CMB", "8000")
    await _create_account(client, auth_headers, "ICBC", "20000")
    payment_id = await _planned_payment(client, auth_headers, "10000")
    await client.post(f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers)

    confirmed = await client.post(
        f"/api/v1/payments/{payment_id}/allocations/confirm", headers=auth_headers
    )
    assert confirmed.status_code == 200
    assert all(a["status"] == "RESERVED" for a in confirmed.json())

    payment = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
    assert payment.json()["status"] == "RESERVED"


async def test_reserved_amount_reflects_in_account_planning(
    client, seeded_banks, auth_headers
) -> None:
    cmb = await _create_account(client, auth_headers, "CMB", "8000")
    await _create_account(client, auth_headers, "ICBC", "20000")
    payment_id = await _planned_payment(client, auth_headers, "10000")
    await client.post(f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers)
    await client.post(f"/api/v1/payments/{payment_id}/allocations/confirm", headers=auth_headers)

    account = await client.get(f"/api/v1/accounts/{cmb}", headers=auth_headers)
    body = account.json()
    assert body["reserved_amount"] == "8000.00"
    assert body["planning_available"] == "0.00"


async def test_manual_override_validates_total(client, seeded_banks, auth_headers) -> None:
    cmb = await _create_account(client, auth_headers, "CMB", "8000")
    icbc = await _create_account(client, auth_headers, "ICBC", "20000")
    payment_id = await _planned_payment(client, auth_headers, "10000")
    await client.post(f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers)

    # Total mismatch (5000 + 4000 != 10000) must be rejected.
    response = await client.put(
        f"/api/v1/payments/{payment_id}/allocations/override",
        headers=auth_headers,
        json=[
            {"account_id": cmb, "amount": "5000.00"},
            {"account_id": icbc, "amount": "4000.00"},
        ],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_manual_override_applies_user_plan(client, seeded_banks, auth_headers) -> None:
    cmb = await _create_account(client, auth_headers, "CMB", "8000")
    icbc = await _create_account(client, auth_headers, "ICBC", "20000")
    payment_id = await _planned_payment(client, auth_headers, "10000")
    await client.post(f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers)

    response = await client.put(
        f"/api/v1/payments/{payment_id}/allocations/override",
        headers=auth_headers,
        json=[
            {"account_id": cmb, "amount": "5000.00"},
            {"account_id": icbc, "amount": "5000.00"},
        ],
    )
    assert response.status_code == 200, response.text
    by_account = {a["account_id"]: a["allocated_amount"] for a in response.json()}
    assert by_account == {cmb: "5000.00", icbc: "5000.00"}


async def test_manual_override_rejects_insufficient_funds(
    client, seeded_banks, auth_headers
) -> None:
    cmb = await _create_account(client, auth_headers, "CMB", "8000")
    icbc = await _create_account(client, auth_headers, "ICBC", "20000")
    payment_id = await _planned_payment(client, auth_headers, "10000")
    await client.post(f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers)

    # CMB only has 8000 available; 9000 from CMB must fail the balance check.
    response = await client.put(
        f"/api/v1/payments/{payment_id}/allocations/override",
        headers=auth_headers,
        json=[
            {"account_id": cmb, "amount": "9000.00"},
            {"account_id": icbc, "amount": "1000.00"},
        ],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "INSUFFICIENT_PLANNING_FUNDS"


async def test_override_requires_allocated_state(client, seeded_banks, auth_headers) -> None:
    await _create_account(client, auth_headers, "CMB", "8000")
    payment_id = await _planned_payment(client, auth_headers, "1000")
    # Never ran preview, so the payment is still PLANNED.
    response = await client.put(
        f"/api/v1/payments/{payment_id}/allocations/override",
        headers=auth_headers,
        json=[{"account_id": "00000000-0000-0000-0000-000000000001", "amount": "1000"}],
    )
    assert response.status_code == 409


async def test_confirm_requires_proposed_allocations(client, seeded_banks, auth_headers) -> None:
    payment_id = await _planned_payment(client, auth_headers, "1000")
    response = await client.post(
        f"/api/v1/payments/{payment_id}/allocations/confirm", headers=auth_headers
    )
    assert response.status_code == 409


async def test_preview_rejects_shortage(client, seeded_banks, auth_headers) -> None:
    await _create_account(client, auth_headers, "CMB", "1000")
    payment_id = await _planned_payment(client, auth_headers, "2000")
    response = await client.post(
        f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "INSUFFICIENT_PLANNING_FUNDS"


async def test_confirm_rechecks_stale_account_balance(client, seeded_banks, auth_headers) -> None:
    account_id = await _create_account(client, auth_headers, "CMB", "8000")
    payment_id = await _planned_payment(client, auth_headers, "8000")
    preview = await client.post(
        f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers
    )
    assert preview.status_code == 200

    changed = await client.put(
        f"/api/v1/accounts/{account_id}",
        headers=auth_headers,
        json={"actual_balance": "1000"},
    )
    assert changed.status_code == 200
    confirmed = await client.post(
        f"/api/v1/payments/{payment_id}/allocations/confirm", headers=auth_headers
    )
    assert confirmed.status_code == 409
    assert confirmed.json()["code"] == "INSUFFICIENT_PLANNING_FUNDS"
