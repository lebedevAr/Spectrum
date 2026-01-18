from pydantic import BaseModel, AnyHttpUrl


class CrawlRequest(BaseModel):
    url: AnyHttpUrl
    max_depth: int = 0
    max_concurrency: int = 5


class PageListItem(BaseModel):
    url: str
    title: str | None


class PageContent(BaseModel):
    url: str
    title: str | None
    html: str
