"""Initialize the local SQLite showcase without Docker or destructive resets."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app.models  # noqa: E402, F401
from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from demo_data import main as seed_demo  # noqa: E402


async def main() -> None:
    if not settings.local_demo:
        raise RuntimeError("This initializer requires LOCAL_DEMO=true and SQLite.")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    if settings.demo_mode:
        await seed_demo(reset=False)
    await engine.dispose()
    print("SQLite showcase ready. Existing data is preserved.")


if __name__ == "__main__":
    asyncio.run(main())
