from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    admin_bot_token: str = Field(alias="ADMIN_BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    superadmin_ids_raw: str = Field(default="", alias="SUPERADMIN_IDS")
    base_bot_username: str = Field(alias="BASE_BOT_USERNAME")
    target_group_id: int = Field(default=0, alias="TARGET_GROUP_ID")
    tracking_task_id: int = Field(default=1, alias="TRACKING_TASK_ID")

    @property
    def superadmin_ids(self) -> set[int]:
        if not self.superadmin_ids_raw.strip():
            return set()
        return {int(x.strip()) for x in self.superadmin_ids_raw.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
