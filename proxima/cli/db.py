from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import text

from proxima.db.migrate import run_migrations
from proxima.logging import configure_logging, get_logger
from proxima.services import build_services
from proxima.settings import get_settings

logger = get_logger(__name__)


@dataclass(slots=True)
class DBOperationOptions:
    migrate: bool = False
    clean: bool = False


async def _clean_db(services) -> None:  # type: ignore[no-untyped-def]
    async with services.db.engine.begin() as conn:
        await conn.execute(text("DELETE FROM mcp_configs"))
        await conn.execute(text("DELETE FROM sessions"))
        await conn.execute(text("DELETE FROM projects"))
    logger.info("database_cleaned")


async def run_db_operations(options: DBOperationOptions) -> None:
    settings = get_settings()
    configure_logging(settings)
    services = build_services(settings)

    try:
        if options.migrate:
            await run_migrations(services.db.engine)
            logger.info("migrations_completed")

        if options.clean:
            await _clean_db(services)
    finally:
        await services.db.close()


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="Database operations")
    parser.add_argument("--migrate", action="store_true", help="Run DB migrations")
    parser.add_argument("--clean", action="store_true", help="Delete all application data")
    args = parser.parse_args()

    if not args.migrate and not args.clean:
        parser.error("at least one action is required: --migrate or --clean")

    asyncio.run(
        run_db_operations(
            DBOperationOptions(
                migrate=args.migrate,
                clean=args.clean,
            )
        )
    )


if __name__ == "__main__":
    main_cli()
