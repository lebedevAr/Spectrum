from sqlalchemy import Text, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base

Base = declarative_base(cls=AsyncAttrs)

class Page(Base):
    __tablename__ = "pages"

    url: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(512))
    html: Mapped[str] = mapped_column(Text)
