import os
from urllib.parse import quote_plus

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from collections.abc import AsyncGenerator
from sqlalchemy import text

from database.db_model_base import DBModelBase


def create_session():
    # 配置 PostgreSQL 连接参数（通过环境变量获取）
    REQUIRED_ENV_VARS = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DATABASE",
    ]

    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]

    if missing:
        raise ValueError(f"Missing environment variables: {missing}")

    # 处理密码中的特殊字符（关键步骤）
    encoded_password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))

    # 构建异步 PostgreSQL 连接 URL
    DATABASE_URL = (
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{encoded_password}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT', '5432')}"
        f"/{os.getenv('POSTGRES_DATABASE')}"
    )

    # 创建异步引擎
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # 调试时可开启，生产环境建议关闭
        pool_size=20,  # 连接池大小
        max_overflow=10,  # 最大溢出连接数
        pool_pre_ping=True,  # 自动检查连接有效性
        pool_timeout=30,
        pool_recycle=3600,
    )

    # 配置异步会话工厂
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,  # 提交后不自动过期对象
        autoflush=False,
    )

    return AsyncSessionLocal, engine


async def get_db(async_session) -> AsyncGenerator[AsyncSession, None]:
    """
    类型安全的异步数据库会话获取
    """
    async with async_session as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        finally:
            await session.close()


async def create_tables(engine) -> None:
    """安全的异步建表方法"""
    try:
        async with engine.begin() as conn:
            # 使用 run_sync 包裹所有同步操作
            await conn.run_sync(DBModelBase.metadata.create_all, checkfirst=True)

            # 异步方式检查表是否存在
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
            existing_tables = result.scalars().all()

            created_tables = [
                t
                for t in DBModelBase.metadata.tables.keys()
                if t not in existing_tables
            ]
            print(f"Created tables: {created_tables or 'None'}")

    except SQLAlchemyError as e:
        print(f"Table creation failed: {str(e)}")
        raise
