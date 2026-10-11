"""FinFlow demo data generator (TASK-061).

Seeds a realistic personal-finance dataset so the UI has something to
show: four bank accounts, recurring bills, and payments in every state
the state machine supports (DRAFT .. MANUALLY_EXECUTED), including two
that run the real allocation engine.

Usage (from the backend directory so `app` is importable):

    cd backend
    uv run python ../scripts/demo_data.py            # create (fails if user exists)
    uv run python ../scripts/demo_data.py --reset     # drop demo user+data, recreate

The script talks to the service layer directly against whatever
DATABASE_URL is configured (dev PostgreSQL by default).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Make the backend package importable when run from either repo root or backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.modules.accounts.models import AccountType
from app.modules.accounts.schemas import AccountCreate
from app.modules.accounts.service import AccountService
from app.modules.allocation.service import AllocationService
from app.modules.auth.demo import DEMO_USER_ID, get_demo_user
from app.modules.auth.models import UserRole
from app.modules.auth.schemas import UserCreate
from app.modules.auth.service import AuthService
from app.modules.forecast.models import CashFlowPlanType
from app.modules.forecast.schemas import CashFlowPlanCreate
from app.modules.forecast.service import ForecastService
from app.modules.payments.models import PaymentPriority, PaymentStatus
from app.modules.payments.schemas import ManualExecution, PaymentCreate
from app.modules.payments.service import PaymentService
from app.modules.recurring.models import RecurringFrequency
from app.modules.recurring.schemas import RecurringCreate
from app.modules.recurring.service import RecurringService
from app.modules.statements.models import StatementImportStatus
from app.modules.statements.service import StatementService

DEMO_USERNAME = "demoowner"
DEMO_EMAIL = "demoowner@finflow.dev"
DEMO_PASSWORD = "demo123456"

TODAY = date.today()


async def _delete_user_data(session, user_id) -> None:
    """Delete a user and everything owned by them, in FK-safe order.

    ``fund_allocations.account_id`` intentionally has no ON DELETE CASCADE
    (money records are never silently dropped), so the reset must remove
    dependent rows explicitly.
    """
    from app.modules.accounts.models import Account, AccountBalanceSnapshot
    from app.modules.allocation.models import FundAllocation
    from app.modules.forecast.models import CashFlowPlan
    from app.modules.payments.models import PaymentPlan
    from app.modules.recurring.models import RecurringPayment
    from app.modules.statements.models import StatementImport, Transaction
    from sqlalchemy import delete, select

    account_ids = list(await session.scalars(select(Account.id).where(Account.user_id == user_id)))

    if account_ids:
        await session.execute(
            delete(FundAllocation).where(FundAllocation.account_id.in_(account_ids))
        )
        await session.execute(
            delete(AccountBalanceSnapshot).where(AccountBalanceSnapshot.account_id.in_(account_ids))
        )
        await session.execute(delete(Transaction).where(Transaction.account_id.in_(account_ids)))
        await session.execute(
            delete(StatementImport).where(StatementImport.account_id.in_(account_ids))
        )
        await session.execute(delete(Account).where(Account.user_id == user_id))

    await session.execute(delete(PaymentPlan).where(PaymentPlan.user_id == user_id))
    await session.execute(delete(RecurringPayment).where(RecurringPayment.user_id == user_id))
    await session.execute(delete(CashFlowPlan).where(CashFlowPlan.user_id == user_id))
    from app.modules.auth.models import User

    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def main(reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        auth = AuthService(session)
        accounts_svc = AccountService(session)
        payments_svc = PaymentService(session)
        recurring_svc = RecurringService(session)
        allocation_svc = AllocationService(session)

        user = (
            await auth.repository.get_by_id(DEMO_USER_ID)
            if settings.demo_mode
            else await auth.repository.get_by_username(DEMO_USERNAME)
        )
        if user is not None:
            demo_empty = settings.demo_mode and not await accounts_svc.list_accounts(user.id)
            if not reset and not demo_empty:
                print(
                    f"User '{user.username}' already has data — use --reset to rebuild demo data."
                )
                return
            if reset:
                print(f"Removing existing demo user {user.username} and dependent data...")
                await _delete_user_data(session, user.id)
                user = None

        if user is None:
            user = (
                await get_demo_user(session)
                if settings.demo_mode
                else await auth.register(
                    UserCreate(
                        username=DEMO_USERNAME,
                        email=DEMO_EMAIL,
                        password=DEMO_PASSWORD,
                    )
                )
            )

        # The demo is meant to show OWNER capabilities (create accounts,
        # run allocations). On a fresh DB the first user becomes OWNER
        # automatically; if the DB has history, force it here so the demo
        # is deterministic. A dev-tool data assignment, not a model change.
        if user.role != UserRole.OWNER:
            user.role = UserRole.OWNER
            await session.commit()
            print(f"Promoted demo user to OWNER: {DEMO_USERNAME}")

        if settings.demo_mode:
            print("Demo mode: open the frontend directly; no login is required.")
        elif user.id is not None:
            print(f"Created demo OWNER: {DEMO_USERNAME} / {DEMO_PASSWORD}")

        # --- Banks / categories --------------------------------------------
        # The app seeds these on startup; on a freshly migrated (empty)
        # database the seed hasn't run yet, so do it here to be robust.
        from app.modules.banks.models import Bank
        from app.modules.banks.seed import seed_default_banks
        from app.modules.categories.seed import seed_default_categories
        from sqlalchemy import select

        await seed_default_banks(session)
        await seed_default_categories(session)

        banks = list(await session.scalars(select(Bank)))
        bank_by_code = {b.code: b for b in banks}
        print(f"Using {len(banks)} seeded banks")

        # --- Accounts ------------------------------------------------------
        def mk(
            bank_code: str,
            name: str,
            balance: str,
            minimum: str,
            atype=AccountType.CHECKING,
        ) -> AccountCreate:
            return AccountCreate(
                bank_id=bank_by_code[bank_code].id,
                name=name,
                masked_account_no=None,
                account_type=atype,
                currency="CNY",
                actual_balance=Decimal(balance),
                minimum_balance=Decimal(minimum),
                include_in_allocation=True,
            )

        accounts = []
        specs = [
            ("CMB", "工资卡（招行）", "128530.42", "10000", AccountType.CHECKING),
            ("ICBC", "房贷账户（工行）", "85200.00", "20000", AccountType.CHECKING),
            ("CCB", "日常消费（建行）", "32410.80", "5000", AccountType.CHECKING),
            ("ICBC", "备用储蓄（工行）", "200000.00", "50000", AccountType.SAVINGS),
        ]
        for bank_code, name, bal, minimum, atype in specs:
            acc = await accounts_svc.create_account(
                user.id, mk(bank_code, name, bal, minimum, atype)
            )
            accounts.append(acc)
            print(f"  account: {acc.name} = {acc.actual_balance}")

        acc_by_key = {acc.name: acc for acc in accounts}

        # --- Recurring bills ----------------------------------------------
        recurring = [
            ("房贷还款", "6200.00", RecurringFrequency.MONTHLY, 1, "房贷账户（工行）"),
            ("房租", "4200.00", RecurringFrequency.MONTHLY, 5, "工资卡（招行）"),
            ("水电网", "380.00", RecurringFrequency.MONTHLY, 15, "日常消费（建行）"),
            ("信用卡还款", "8000.00", RecurringFrequency.MONTHLY, 20, "工资卡（招行）"),
            ("话费", "129.00", RecurringFrequency.MONTHLY, 8, "日常消费（建行）"),
        ]
        for name, amount, freq, dom, pref in recurring:
            await recurring_svc.create(
                user.id,
                RecurringCreate(
                    name=name,
                    amount=Decimal(amount),
                    currency="CNY",
                    frequency=freq,
                    day_of_month=dom,
                    start_date=TODAY - timedelta(days=30),
                    preferred_account_id=acc_by_key[pref].id,
                    priority=PaymentPriority.HIGH if dom == 1 else PaymentPriority.NORMAL,
                ),
            )
        print(f"  recurring bills: {len(recurring)}")

        # --- Payments across the state machine -----------------------------
        def pay(
            name: str,
            amount: str,
            days: int,
            priority=PaymentPriority.NORMAL,
            preferred=None,
        ):
            return PaymentCreate(
                name=name,
                amount=Decimal(amount),
                currency="CNY",
                planned_date=TODAY + timedelta(days=days),
                priority=priority,
                preferred_account_id=preferred,
            )

        # DRAFT
        p_draft = await payments_svc.create_payment(user.id, pay("新手机分期", "6999.00", 25))
        print(f"  payment DRAFT: {p_draft.name}")

        # PLANNED
        p_planned = await payments_svc.create_payment(
            user.id,
            pay(
                "车险续费",
                "5800.00",
                10,
                PaymentPriority.HIGH,
                acc_by_key["工资卡（招行）"].id,
            ),
        )
        await payments_svc.transition(user.id, p_planned.id, PaymentStatus.PLANNED)
        print(f"  payment PLANNED: {p_planned.name}")

        # ALLOCATED (real allocation engine)
        p_alloc = await payments_svc.create_payment(user.id, pay("家庭聚餐基金", "3000.00", 6))
        await payments_svc.transition(user.id, p_alloc.id, PaymentStatus.PLANNED)
        await allocation_svc.generate_preview(user.id, p_alloc.id)
        print(f"  payment ALLOCATED: {p_alloc.name}")

        # RESERVED (preview + confirm = virtual reservation)
        p_reserved = await payments_svc.create_payment(
            user.id,
            pay("季度物业费", "2400.00", 15, preferred=acc_by_key["备用储蓄（工行）"].id),
        )
        await payments_svc.transition(user.id, p_reserved.id, PaymentStatus.PLANNED)
        await allocation_svc.generate_preview(user.id, p_reserved.id)
        await allocation_svc.confirm_reservation(user.id, p_reserved.id)
        print(f"  payment RESERVED: {p_reserved.name}")

        # WAITING_MANUAL_EXECUTION
        p_waiting = await payments_svc.create_payment(
            user.id,
            pay("牙科检查", "1200.00", 3, preferred=acc_by_key["日常消费（建行）"].id),
        )
        await payments_svc.transition(user.id, p_waiting.id, PaymentStatus.PLANNED)
        await allocation_svc.generate_preview(user.id, p_waiting.id)
        await allocation_svc.confirm_reservation(user.id, p_waiting.id)
        await payments_svc.transition(user.id, p_waiting.id, PaymentStatus.WAITING_MANUAL_EXECUTION)
        print(f"  payment WAITING_MANUAL_EXECUTION: {p_waiting.name}")

        # MANUALLY_EXECUTED
        p_done = await payments_svc.create_payment(
            user.id,
            pay("宽带续费", "600.00", -5, preferred=acc_by_key["日常消费（建行）"].id),
        )
        await payments_svc.transition(user.id, p_done.id, PaymentStatus.PLANNED)
        await allocation_svc.generate_preview(user.id, p_done.id)
        await allocation_svc.confirm_reservation(user.id, p_done.id)
        await payments_svc.transition(user.id, p_done.id, PaymentStatus.WAITING_MANUAL_EXECUTION)
        await payments_svc.manual_execution(
            user.id,
            p_done.id,
            ManualExecution(
                executed_at=None,
                account_id=acc_by_key["日常消费（建行）"].id,
                bank_reference="CMB-20260807-0032",
                note="网银手动续费",
            ),
        )
        print(f"  payment MANUALLY_EXECUTED: {p_done.name}")

        # Multi-currency forecasts and transaction history for the showcase.
        usd_account = await accounts_svc.create_account(
            user.id,
            AccountCreate(
                bank_id=bank_by_code["BOC"].id,
                name="模拟美元储蓄",
                currency="USD",
                actual_balance=Decimal("1200.00"),
                minimum_balance=Decimal("200.00"),
                include_in_allocation=True,
            ),
        )
        forecast_svc = ForecastService(session)
        for name, amount, currency, account_id, days in [
            ("模拟下期工资", "20000.00", "CNY", accounts[0].id, 7),
            ("模拟美元收入", "200.00", "USD", usd_account.id, 14),
            ("模拟待归属收入", "800.00", "CNY", None, 10),
        ]:
            await forecast_svc.create_plan(
                user.id,
                CashFlowPlanCreate(
                    type=CashFlowPlanType.INCOME,
                    name=name,
                    amount=Decimal(amount),
                    currency=currency,
                    account_id=account_id,
                    date=TODAY + timedelta(days=days),
                ),
            )
        csv = (
            "交易日期,摘要,对方户名,交易流水号,收入金额,支出金额,余额\n"
            f"{TODAY - timedelta(days=2)},模拟工资入账,模拟科技公司,"
            "DEMO-SALARY,20000.00,,128530.42\n"
            f"{TODAY - timedelta(days=1)},模拟日常消费,模拟超市,DEMO-SHOP,,120.50,128409.92\n"
        )
        statements_svc = StatementService(session)
        imported = await statements_svc.upload(
            user.id, accounts[0].id, "demo-history.csv", csv.encode("utf-8-sig")
        )
        processed = await statements_svc.process_import(imported.import_id)
        if processed.status != StatementImportStatus.SUCCESS:
            raise RuntimeError("Demo statement parsing failed; inspect the import errors.")
        print("  cash flow plans: 3; demo statement transactions: 2; currencies: CNY/USD")

        print()
        if settings.demo_mode:
            print("Demo data ready. Open the frontend directly without logging in.")
        else:
            print("Demo data ready. Login:")
            print(f"  username : {DEMO_USERNAME}")
            print(f"  password : {DEMO_PASSWORD}")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    asyncio.run(main(reset))
