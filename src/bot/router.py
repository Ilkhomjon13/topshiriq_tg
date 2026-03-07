from aiogram import Router

from src.bot.handlers.admin import router as admin_router
from src.bot.handlers.group_tracking import router as group_tracking_router
from src.bot.handlers.user import router as user_router


def register_routers(main_router: Router) -> None:
    main_router.include_router(group_tracking_router)
    main_router.include_router(user_router)
    main_router.include_router(admin_router)
