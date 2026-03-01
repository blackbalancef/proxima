from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_permission_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Allow", callback_data=f"perm:allow:{request_id}"),
                InlineKeyboardButton(text="Deny", callback_data=f"perm:deny:{request_id}"),
            ],
            [
                InlineKeyboardButton(
                    text="Allow All Session",
                    callback_data=f"perm:allow_all:{request_id}",
                )
            ],
        ]
    )


def build_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Plan", callback_data="mode:plan"),
                InlineKeyboardButton(text="Execute", callback_data="mode:execute"),
            ]
        ]
    )


MODEL_OPTIONS: list[tuple[str, str]] = [
    ("claude-opus-4-6", "Opus"),
    ("claude-sonnet-4-6", "Sonnet"),
    ("claude-haiku-4-5", "Haiku"),
]


def build_model_keyboard(current: str | None) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    for model_id, label in MODEL_OPTIONS:
        prefix = "-> " if model_id == current else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{prefix}{label}",
                callback_data=f"model:{model_id}",
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def build_update_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Update & Restart", callback_data="update:confirm"
                ),
                InlineKeyboardButton(text="Cancel", callback_data="update:cancel"),
            ]
        ]
    )


def build_project_keyboard(
    projects: list[dict[str, int | str]],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for project in projects:
        rows.append(
            [
                InlineKeyboardButton(
                    text=str(project["name"]),
                    callback_data=f"project:thread:{project['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
