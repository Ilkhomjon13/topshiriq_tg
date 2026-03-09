from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def pending_request_inline(certificate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tasdiqlash", callback_data=f"admin:approve:{certificate_id}")],
            [InlineKeyboardButton(text="Rad etish", callback_data=f"admin:reject:{certificate_id}")],
        ]
    )
