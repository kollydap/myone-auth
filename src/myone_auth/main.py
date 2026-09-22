from contextlib import asynccontextmanager
from fastapi import FastAPI
from myone_auth.core.database import engine
from myone_auth.core.logging import configure_logging
from myone_auth.core.middleware import RequestIdMiddleware
from myone_auth.routers.health import router as health_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
app.include_router(
    prefix="/health",
    tags=["Health"],
    router=health_router,
)
