"""Transaction deduplication via stable fingerprints.

A fingerprint is a SHA-256 over the meaningful transaction fields. It must
NOT rely on amount+date alone — legitimate duplicate spending exists (two
identical coffees the same day). Description and external reference are
included, lightly normalized so cosmetic whitespace/case differences still
match.
"""

import hashlib
import re
from datetime import date
from decimal import Decimal

from app.modules.statements.parsers.base import ParsedTransaction


def _fingerprint_text(value: str | None) -> str:
    """Light normalization for fingerprint inputs (no punctuation loss)."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def compute_fingerprint(
    *,
    account_id: str,
    transaction_date: date | None,
    amount: Decimal,
    direction: str,
    description: str,
    external_reference: str | None = None,
) -> str:
    """Return a stable SHA-256 hex fingerprint for a transaction."""
    payload = "|".join(
        [
            str(account_id),
            transaction_date.isoformat() if transaction_date else "",
            format(amount, "f"),
            direction,
            _fingerprint_text(description),
            _fingerprint_text(external_reference),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def transaction_fingerprint(account_id: str, txn: ParsedTransaction) -> str:
    """Fingerprint a parsed transaction for an account."""
    return compute_fingerprint(
        account_id=account_id,
        transaction_date=txn.transaction_date,
        amount=txn.amount,
        direction=txn.direction.value if txn.direction else "",
        description=txn.description,
        external_reference=txn.reference,
    )
