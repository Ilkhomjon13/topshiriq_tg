from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def task_list_inline(tasks: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title, callback_data=f"task:view:{task_id}")] for task_id, title in tasks]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def task_detail_inline(task_id: int, is_joined: bool = False) -> InlineKeyboardMarkup:
    join_text = "✅ Siz qatnashyapsiz" if is_joined else "✅ Qatnashish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=join_text, callback_data=f"task:join:{task_id}")],
            [InlineKeyboardButton(text="ℹ️ Qoidalar", callback_data=f"task:rules:{task_id}")],
            [InlineKeyboardButton(text="🎁 Sovg'alar", callback_data=f"task:rewards:{task_id}")],
            [InlineKeyboardButton(text="📈 Progressim", callback_data=f"task:progress:{task_id}")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="task:back")],
        ]
    )


def certificate_use_inline(certificate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎁 Foydalanish", callback_data=f"cert:use:{certificate_id}")]]
    )


def confirm_use_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlayman", callback_data="cert:confirm")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cert:cancel")],
        ]
    )


def pending_request_inline(certificate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin:approve:{certificate_id}")],
            [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin:reject:{certificate_id}")],
        ]
    )
