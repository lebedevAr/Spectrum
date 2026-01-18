from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.database import AsyncSessionLocal
from app.models import Page
from app.schemas import CrawlRequest, PageListItem, PageContent
from app.crawler import crawl

router = APIRouter()


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/crawl")
async def start_crawl(req: CrawlRequest):
    asyncio.create_task(
        crawl(
            start_url=str(req.url),
            max_depth=req.max_depth,
            max_concurrency=req.max_concurrency,
        )
    )
    return {"status": "crawl started"}


@router.get("/pages", response_model=list[PageListItem])
async def list_pages(
        q: str | None = Query(None),
        session: AsyncSession = Depends(get_session),
):
    stmt = select(Page.url, Page.title)

    if q:
        stmt = stmt.where(
            or_(
                Page.url.ilike(f"%{q}%"),
                Page.title.ilike(f"%{q}%"),
            )
        )

    res = await session.execute(stmt)
    return res.all()


@router.get("/pages/content", response_model=PageContent)
async def get_page_content(
        url: str,
        session: AsyncSession = Depends(get_session),
):
    page = await session.get(Page, url)
    if not page:
        raise HTTPException(404, "Page not found")

    return page
