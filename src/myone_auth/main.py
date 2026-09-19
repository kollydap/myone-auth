from contextlib import asynccontextmanager
from fastapi import FastAPI
from myone_auth.core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    
app = FastAPI(lifespan=lifespan)
