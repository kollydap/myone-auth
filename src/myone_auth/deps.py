from myone_auth.core.database import session_factory


async def get_db():
    """
    Dependency that provides a database session for each request.
    """
    async with session_factory() as session:
        yield session
