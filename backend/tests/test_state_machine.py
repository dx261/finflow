"""Payment state machine tests."""

import pytest
from app.core.exceptions import InvalidStateTransitionError
from app.modules.payments.models import PaymentStatus
from app.modules.payments.state_machine import assert_transition, can_transition

S = PaymentStatus

HAPPY_PATH = [
    (S.DRAFT, S.PLANNED),
    (S.PLANNED, S.ALLOCATED),
    (S.ALLOCATED, S.RESERVED),
    (S.RESERVED, S.WAITING_MANUAL_EXECUTION),
    (S.WAITING_MANUAL_EXECUTION, S.MANUALLY_EXECUTED),
    (S.MANUALLY_EXECUTED, S.RECONCILING),
    (S.RECONCILING, S.SETTLED),
]


def test_normal_path_is_legal() -> None:
    for current, target in HAPPY_PATH:
        assert can_transition(current, target), f"{current} -> {target}"


def test_exception_path_legal() -> None:
    assert can_transition(S.MANUALLY_EXECUTED, S.EXCEPTION)
    assert can_transition(S.RECONCILING, S.EXCEPTION)


def test_cancel_paths_legal() -> None:
    assert can_transition(S.PLANNED, S.CANCELLED)
    assert can_transition(S.RESERVED, S.CANCELLED)
    assert can_transition(S.WAITING_MANUAL_EXECUTION, S.CANCELLED)


def test_settled_to_draft_forbidden() -> None:
    # The plan explicitly forbids SETTLED -> DRAFT.
    assert not can_transition(S.SETTLED, S.DRAFT)
    with pytest.raises(InvalidStateTransitionError):
        assert_transition(S.SETTLED, S.DRAFT)


def test_skipping_states_forbidden() -> None:
    assert not can_transition(S.DRAFT, S.SETTLED)
    assert not can_transition(S.DRAFT, S.RESERVED)
    assert not can_transition(S.ALLOCATED, S.MANUALLY_EXECUTED)


def test_terminal_states_have_no_outgoing() -> None:
    assert can_transition(S.SETTLED, S.DRAFT) is False
    for state in (S.SETTLED, S.CANCELLED, S.EXCEPTION):
        for target in S:
            assert can_transition(state, target) is False


# --- API-level tests ------------------------------------------------------


async def _create_payment(client, auth_headers) -> str:
    response = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "房租", "amount": "8000.00", "planned_date": "2026-10-01"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_transition_endpoint_happy_path(client, seeded_banks, auth_headers) -> None:
    payment_id = await _create_payment(client, auth_headers)

    response = await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "PLANNED"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PLANNED"


async def test_transition_endpoint_rejects_illegal(client, seeded_banks, auth_headers) -> None:
    payment_id = await _create_payment(client, auth_headers)
    # DRAFT -> SETTLED is illegal.
    response = await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "SETTLED"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_STATE_TRANSITION"


async def test_side_effect_transitions_require_domain_endpoints(
    client, seeded_banks, auth_headers
) -> None:
    payment_id = await _create_payment(client, auth_headers)
    planned = await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "PLANNED"},
    )
    assert planned.status_code == 200

    allocated = await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "ALLOCATED"},
    )
    assert allocated.status_code == 409
    assert allocated.json()["code"] == "CONFLICT"
