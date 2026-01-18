from fastapi import FastAPI
from app.api import router
from app.database import engine
from app.models import Base

app = FastAPI(title="Async Web Crawler")

app.include_router(router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
