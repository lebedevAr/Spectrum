import asyncio
import logging
import httpx

from collections import deque
from bs4 import BeautifulSoup

from urllib.parse import urljoin, urlparse, urlunparse
from sqlalchemy.dialects.postgresql import insert

from app.database import AsyncSessionLocal
from app.models import Page

logger = logging.getLogger("crawler")
logging.basicConfig(level=logging.INFO)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


async def fetch_page(client: httpx.AsyncClient, url: str) -> tuple[str | None, str, list[str]]:
    resp = await client.get(url, timeout=10)
    resp.raise_for_status()

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title else None

    links: list[str] = []
    for a in soup.find_all("a", href=True):
        raw_link = a["href"]

        if raw_link.startswith(("mailto:", "tel:")):
            continue

        link = urljoin(url, raw_link)
        link = normalize_url(link)

        parsed = urlparse(link)

        if parsed.scheme not in {"http", "https"}:
            continue

        if parsed.path.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".zip", ".rar", ".css", ".js",)):
            continue

        links.append(link)

    return title, html, links


async def crawl(
        start_url: str,
        max_depth: int,
        max_concurrency: int,
):
    start_url = normalize_url(start_url)
    start_domain = urlparse(start_url).netloc

    logger.info(
        "Crawl started: %s | max_depth=%d | concurrency=%d",
        start_url,
        max_depth,
        max_concurrency,
    )

    semaphore = asyncio.Semaphore(max_concurrency)
    visited: set[str] = set()

    url_queue: deque[tuple[str, int]] = deque()
    url_queue.append((start_url, 0))

    db_queue: asyncio.Queue = asyncio.Queue()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async def db_writer():
            async with AsyncSessionLocal() as session:
                while True:
                    item = await db_queue.get()
                    if item is None:
                        break

                    url, title, html = item

                    await session.execute(
                        insert(Page)
                        .values(url=url, title=title, html=html)
                        .on_conflict_do_nothing(index_elements=["url"])
                    )
                    await session.commit()

                    db_queue.task_done()

        async def worker():
            while url_queue:
                url, depth = url_queue.popleft()

                if url in visited or depth > max_depth:
                    continue

                visited.add(url)

                async with semaphore:
                    try:
                        title, html, links = await fetch_page(client, url)
                        logger.info("Fetched: %s (depth=%d)", url, depth)
                    except Exception as e:
                        logger.warning("Failed: %s (%s)", url, e)
                        continue

                await db_queue.put((url, title, html))

                if depth < max_depth:
                    for link in links:
                        parsed = urlparse(link)

                        if parsed.netloc != start_domain:
                            continue

                        if link not in visited:
                            url_queue.append((link, depth + 1))

        writer_task = asyncio.create_task(db_writer())
        workers = [
            asyncio.create_task(worker())
            for _ in range(max_concurrency)
        ]
        await asyncio.gather(*workers)

        await db_queue.join()
        await db_queue.put(None)
        await writer_task

    logger.info(
        "Crawl finished: %s | pages=%d",
        start_url,
        len(visited),
    )
