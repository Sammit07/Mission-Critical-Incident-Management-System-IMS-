from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "Incident Management System"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://ims_user:ims_password@localhost:5432/ims_db"
    MONGODB_URL: str = "mongodb://ims_user:ims_password@localhost:27017/ims_signals?authSource=admin"
    REDIS_URL: str = "redis://localhost:6379"

    CORS_ORIGINS: str = "http://localhost:3000"

    # In-memory queue — large enough to absorb 10k signals/sec bursts while DB is slow
    SIGNAL_QUEUE_MAXSIZE: int = 500_000
    SIGNAL_WORKER_COUNT: int = 10

    # Debouncing: one work item per component per window
    DEBOUNCE_WINDOW_SECONDS: int = 10

    # Rate limiting on /api/signals
    RATE_LIMIT_REQUESTS: int = 10_000
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    METRICS_INTERVAL_SECONDS: int = 5

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env"}


settings = Settings()
