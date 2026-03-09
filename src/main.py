import asyncio

from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from src.bot.router import register_routers
from src.core.config import get_settings
from src.db.base import Base
from src.db.session import SessionLocal, engine
from src.services.auth_service import ensure_superadmins
from src.services.seed_service import ensure_seed_data


async def _startup() -> None:
    settings = get_settings()
    if settings.run_db_init:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        await ensure_superadmins(db, telegram_ids=settings.superadmin_ids)
        if settings.run_seed:
            await ensure_seed_data(db)
        await db.commit()


async def main() -> None:
    settings = get_settings()
    await _startup()

    bot = Bot(token=settings.bot_token)
    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)

    dp = Dispatcher(storage=storage)
    root_router = Router()
    register_routers(root_router)
    dp.include_router(root_router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
