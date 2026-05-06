from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/async_docs"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "./storage"


settings = Settings()
