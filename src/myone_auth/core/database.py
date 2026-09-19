from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from myone_auth.core.config import get_settings

settings = get_settings()

sql_url = settings.database_url.get_secret_value()
engine = create_async_engine(sql_url)

session_factory = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)
