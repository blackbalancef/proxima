from __future__ import annotations

from pathlib import Path

DEFAULT_DATABASE_URL = "postgresql://proxima:dev@localhost:5432/proxima"


def main_cli() -> None:
    env_path = Path(".env")
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""

    print("Proxima setup wizard\n")
    telegram_token = input("Telegram bot token: ").strip()
    user_ids = input("Allowed Telegram user IDs (comma separated): ").strip()
    openai_key = input("OpenAI API key (optional): ").strip()
    work_dir = input("Work dir (optional, default cwd): ").strip()

    lines = [
        "# Telegram Bot",
        f"TELEGRAM_BOT_TOKEN={telegram_token}",
        "",
        "# Access control",
        f"ALLOWED_USER_IDS={user_ids}",
        "",
        "# Working directory",
        f"WORK_DIR={work_dir}" if work_dir else "# WORK_DIR=/path/to/projects",
        "",
        "# OpenAI for voice transcription",
        f"OPENAI_API_KEY={openai_key}" if openai_key else "# OPENAI_API_KEY=",
        "",
        "# PostgreSQL",
        f"DATABASE_URL={DEFAULT_DATABASE_URL}",
        "",
        "# Logging",
        "LOG_LEVEL=info",
        "",
    ]

    env_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {env_path.resolve()}")

    if existing:
        print("Previous .env content has been replaced.")


if __name__ == "__main__":
    main_cli()
