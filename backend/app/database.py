import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from .config import settings

logger = logging.getLogger(__name__)

# ── PostgreSQL ────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


# ── MongoDB ───────────────────────────────────────────────────────────────────
mongo_client: AsyncIOMotorClient | None = None
mongo_db = None

# ── Redis ─────────────────────────────────────────────────────────────────────
redis_client: Redis | None = None


async def init_postgres() -> None:
    from .models.db_models import Base as ModelBase  # noqa: F401 — registers all ORM models

    async with engine.begin() as conn:
        await conn.run_sync(ModelBase.metadata.create_all)
    logger.info("PostgreSQL tables created/verified")


async def init_mongodb() -> None:
    global mongo_client, mongo_db
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    mongo_db = mongo_client.get_database("ims_signals")

    await mongo_db.signals.create_index([("work_item_id", 1)])
    await mongo_db.signals.create_index([("component_id", 1), ("timestamp", -1)])
    await mongo_db.signals.create_index([("timestamp", -1)])
    logger.info("MongoDB initialized with indexes")


async def init_redis() -> None:
    global redis_client
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.ping()
    logger.info("Redis connected")


async def close_connections() -> None:
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.aclose()
    await engine.dispose()


def get_db() -> async_sessionmaker:
    return AsyncSessionLocal


def get_mongo_db():
    return mongo_db


def get_redis() -> Redis | None:
    return redis_client
