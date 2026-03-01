from proxima.settings import Settings


def _base_kwargs() -> dict[str, object]:
    return {
        "telegram_bot_token": "123:abc",
        "database_url": "postgresql://user:pass@localhost:5432/db",
    }


def test_allowed_user_ids_accepts_single_int() -> None:
    settings = Settings(**_base_kwargs(), allowed_user_ids=272770135)
    assert settings.allowed_user_ids == [272770135]


def test_allowed_user_ids_accepts_csv_string() -> None:
    settings = Settings(**_base_kwargs(), allowed_user_ids="1,2,3")
    assert settings.allowed_user_ids == [1, 2, 3]
