"""Payment state machine.

Every status change goes through this module — routers and services must
never assign ``payment.status`` directly. Illegal transitions (e.g.
``SETTLED -> DRAFT``) are rejected with
:class:`InvalidStateTransitionError`.
"""

from app.core.exceptions import InvalidStateTransitionError
from app.modules.payments.models import PaymentStatus

TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.DRAFT: {PaymentStatus.PLANNED},
    PaymentStatus.PLANNED: {PaymentStatus.ALLOCATED, PaymentStatus.CANCELLED},
    PaymentStatus.ALLOCATED: {PaymentStatus.RESERVED},
    # RESERVED -> PLANNED is the reservation-release path (§50).
    PaymentStatus.RESERVED: {
        PaymentStatus.WAITING_MANUAL_EXECUTION,
        PaymentStatus.CANCELLED,
        PaymentStatus.PLANNED,
    },
    PaymentStatus.WAITING_MANUAL_EXECUTION: {
        PaymentStatus.MANUALLY_EXECUTED,
        PaymentStatus.CANCELLED,
        PaymentStatus.PLANNED,
    },
    PaymentStatus.MANUALLY_EXECUTED: {
        PaymentStatus.RECONCILING,
        PaymentStatus.EXCEPTION,
    },
    PaymentStatus.RECONCILING: {PaymentStatus.SETTLED, PaymentStatus.EXCEPTION},
    PaymentStatus.EXCEPTION: set(),
    PaymentStatus.SETTLED: set(),
    PaymentStatus.CANCELLED: set(),
}


def can_transition(current: PaymentStatus, target: PaymentStatus) -> bool:
    """Return whether the given status transition is legal."""
    return target in TRANSITIONS.get(current, set())


def assert_transition(current: PaymentStatus, target: PaymentStatus) -> None:
    """Raise if the transition is illegal."""
    if not can_transition(current, target):
        raise InvalidStateTransitionError(
            f"Cannot transition payment from {current.value} to {target.value}."
        )
