"""FinFlow end-to-end test (TASK-055).

Drives the complete user journey through the live HTTP API against the
real PostgreSQL + Redis stack, asserting every step and the unified error
format. This complements the 200+ unit tests with a full-integration
check.

Prerequisites: the backend must be running (dev or production).

    cd backend
    uv run uvicorn app.main:app --port 8000          # or docker compose up
    uv run python ../scripts/e2e_test.py
    BASE_URL=http://localhost:8000 uv run python ../scripts/e2e_test.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
PREFIX = f"{BASE_URL}/api/v1"

OWNER = {"username": "demoowner", "password": "demo123456"}

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if ok:
        passed += 1
    else:
        failed += 1


def get(client: httpx.Client, path: str, token: str | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(f"{PREFIX}{path}", headers=headers)


def post(client: httpx.Client, path: str, json=None, token: str | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(f"{PREFIX}{path}", json=json, headers=headers)


def put(client: httpx.Client, path: str, json=None, token: str | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.put(f"{PREFIX}{path}", json=json, headers=headers)


def main() -> int:
    stamp = date.today().strftime("%Y%m%d%H%M")
    viewer_user = f"e2e_viewer_{stamp}"
    viewer_email = f"{viewer_user}@e2e.dev"

    with httpx.Client(timeout=30) as client:
        # --- 0. Health -----------------------------------------------------
        print("== health ==")
        r = get(client, "/health")
        check("health ok", r.status_code == 200 and r.json().get("status") == "ok")

        # --- 1. Auth --------------------------------------------------------
        print("== auth ==")
        r = post(client, "/auth/register", {"username": viewer_user, "email": viewer_email, "password": "e2epass123"})
        check("register viewer", r.status_code == 201, r.text)
        viewer_role = r.json().get("role")
        check("registered user is VIEWER", viewer_role == "VIEWER", str(viewer_role))

        r = post(client, "/auth/register", {"username": viewer_user, "email": f"x{viewer_email}", "password": "e2epass123"})
        check("duplicate username -> 409", r.status_code == 409 and r.json().get("code") == "CONFLICT")

        r = post(client, "/auth/login", {"login": OWNER["username"], "password": OWNER["password"]})
        check("owner login", r.status_code == 200)
        owner_token = r.json()["access_token"]

        r = post(client, "/auth/login", {"login": viewer_user, "password": "e2epass123"})
        viewer_token = r.json()["access_token"]

        r = get(client, "/auth/me", owner_token)
        check("me returns OWNER", r.status_code == 200 and r.json().get("role") == "OWNER")

        r = get(client, "/accounts")
        check("no token -> 401 + unified format",
              r.status_code == 401 and set(r.json().keys()) == {"code", "message", "trace_id"})

        # --- 2. OWNER journey ------------------------------------------------
        print("== owner journey ==")
        r = get(client, "/accounts", owner_token)
        accounts_before = r.json()
        check("list accounts", r.status_code == 200 and len(accounts_before) >= 4, r.text)

        r = get(client, "/banks", owner_token)
        check("list banks", r.status_code == 200 and any(b["code"] == "ICBC" for b in r.json()))
        icbc = next(b["id"] for b in r.json() if b["code"] == "ICBC")

        # Account creation.
        r = post(client, "/accounts", {"bank_id": icbc, "name": f"E2E Account {stamp}", "currency": "CNY", "actual_balance": "100000.00", "minimum_balance": "10000"}, owner_token)
        check("create account", r.status_code == 201, r.text)
        account = r.json()
        account_id = account["id"]
        check("planning_available computed", account["planning_available"] == "90000.00", account["planning_available"])

        # Payment lifecycle.
        r = post(client, "/payments", {"name": f"E2E Bill {stamp}", "amount": "3000.00", "currency": "CNY", "planned_date": str(date.today() + timedelta(days=7)), "preferred_account_id": account_id}, owner_token)
        check("create payment", r.status_code == 201, r.text)
        payment = r.json()
        payment_id = payment["id"]

        r = post(client, f"/payments/{payment_id}/transition", {"target_status": "PLANNED"}, owner_token)
        check("transition to PLANNED", r.json().get("status") == "PLANNED", r.text)

        r = post(client, f"/payments/{payment_id}/allocations/preview", token=owner_token)
        check("allocation preview", r.status_code == 200 and len(r.json()) > 0, r.text)

        r = post(client, f"/payments/{payment_id}/allocations/confirm", token=owner_token)
        check("allocation confirm -> RESERVED", r.json()[0]["status"] == "RESERVED", r.text)

        r = post(client, f"/payments/{payment_id}/transition", {"target_status": "WAITING_MANUAL_EXECUTION"}, owner_token)
        check("transition to WAITING", r.json().get("status") == "WAITING_MANUAL_EXECUTION", r.text)

        r = post(client, f"/payments/{payment_id}/manual-execution", {"account_id": account_id, "note": "e2e", "bank_reference": f"E2E-{stamp}"}, owner_token)
        check("manual execution", r.json().get("status") == "MANUALLY_EXECUTED", r.text)

        # Statement import (real file, sync worker required for full run).
        print("== statement import ==")
        csv_path = Path(os.environ.get("TMP", "/tmp")) / f"e2e_statement_{stamp}.csv"
        rows = [
            ["交易日期", "摘要", "对方户名", "收入金额", "支出金额", "余额"],
            [str(date.today() - timedelta(days=1)), "工资", "E2E Corp", "10000.00", "", "110000.00"],
            [str(date.today() - timedelta(days=2)), "超市", "E2E Mart", "", "123.45", "100000.00"],
        ]
        csv_path.write_text("\n".join(",".join(r) for r in rows) + "\n", encoding="utf-8-sig")

        with open(csv_path, "rb") as fh:
            r = client.post(
                f"{PREFIX}/statements/upload",
                headers={"Authorization": f"Bearer {owner_token}"},
                data={"account_id": account_id},
                files={"file": (csv_path.name, fh, "text/csv")},
            )
        check("upload statement", r.status_code == 202 and not r.json()["is_duplicate"], r.text)
        import_id = r.json()["import_id"]

        # Poll until the worker finishes (or give up after ~20s).
        status = "UPLOADED"
        for _ in range(20):
            time.sleep(2)
            detail = get(client, f"/statements/{import_id}", owner_token)
            if detail.status_code != 200:
                break
            status = detail.json()["import_record"]["status"]
            if status in ("SUCCESS", "PARTIAL_SUCCESS", "FAILED"):
                break
        check(f"import completes ({status})", status in ("SUCCESS", "PARTIAL_SUCCESS"))

        r = get(client, "/transactions", owner_token)
        check("transactions searchable", r.status_code == 200 and len(r.json()) > 0)

        # Forecast.
        r = get(client, "/forecast?days=30", owner_token)
        check("forecast 30d", r.status_code == 200 and "aggregate" in r.json(), r.text)

        # --- 3. VIEWER restrictions ------------------------------------------
        print("== viewer restrictions ==")
        r = post(client, "/accounts", {"bank_id": icbc, "name": "Blocked", "currency": "CNY", "actual_balance": "1"}, viewer_token)
        check("viewer cannot create account -> 403", r.status_code == 403 and r.json().get("code") == "FORBIDDEN")
        r = post(client, "/payments", {"name": "Blocked", "amount": "1.00", "currency": "CNY", "planned_date": "2026-12-01"}, viewer_token)
        check("viewer cannot create payment -> 403", r.status_code == 403)
        r = get(client, "/accounts", viewer_token)
        check("viewer can read accounts", r.status_code == 200)

    print()
    print(f"E2E result: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
