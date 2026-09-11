"""Central model registration.

Importing this module registers every ORM model on ``Base.metadata`` so
foreign keys always resolve, regardless of which process (API, worker,
alembic) is running. Import it early in every entrypoint.
"""

from app.core.database import Base  # noqa: F401
from app.modules.accounts.models import Account, AccountBalanceSnapshot  # noqa: F401
from app.modules.allocation.models import FundAllocation  # noqa: F401
from app.modules.audit.models import AuditLog  # noqa: F401
from app.modules.auth.models import User  # noqa: F401
from app.modules.banks.models import Bank  # noqa: F401
from app.modules.categories.models import Category  # noqa: F401
from app.modules.payments.models import PaymentPlan  # noqa: F401
from app.modules.reconciliation.models import Reconciliation  # noqa: F401
from app.modules.recurring.models import RecurringPayment  # noqa: F401
from app.modules.statements.models import ImportError, StatementImport, Transaction  # noqa: F401
