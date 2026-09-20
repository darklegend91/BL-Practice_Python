"""The whole API. No accounts, no tokens, no headers to remember.

    GET  /              what this project is and how to use it
    GET  /options       what you are allowed to choose
    POST /recommend     send your choices, get an answer back
    GET  /recommend     what to send to POST /recommend
    GET  /catalog       the data the answer was based on
    GET  /pages         the pages the crawler stored
    GET  /sources       the pages the crawler visits
    POST /sources       register one
    GET  /sources/help  what to send to POST /sources
    POST /crawl         fetch the sources again now
    GET  /crawl         what POST /crawl does
    GET  /health        is the app up and is the database reachable

``POST /recommend`` is the one that matters. Every POST has a GET beside it
that tells you what to send, and ``GET /`` explains the whole thing.
"""

from __future__ import annotations

import asyncio

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import catalog as catalog_loader, crawler, help as help_text
from app.db import Page, Source, get_session
from app.engine.recommend import recommend
from app.help import EndpointHelp, FieldHelp, Home
from app.options import all_options
from app.schemas import Catalog, RecommendInput, Result, Strict
from app.version import APP_VERSION

app = FastAPI(
    title="LLM Fit Advisor",
    version=APP_VERSION,
    description=(
        "Tells you whether to run a language model on your own computer or pay for "
        "a subscription. Pick from options, get an answer with the reasoning shown. "
        "No login. The app runs no model itself and calls no model API."
    ),
)


# --------------------------------------------------------------------------- #
# Errors: one predictable shape
# --------------------------------------------------------------------------- #


def _problem(status_code: int, message: str, fields: list[dict] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": message, "fields": fields or []},
    )


@app.exception_handler(RequestValidationError)
async def _bad_request(request: Request, error: RequestValidationError):
    return _problem(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Some of what you sent is not a valid choice. See 'fields', and GET /options "
        "for the list of what is allowed.",
        [
            {
                "field": ".".join(str(part) for part in item.get("loc", ()) if part != "body"),
                "problem": item.get("msg", "invalid"),
            }
            for item in error.errors()
        ],
    )


@app.exception_handler(ValidationError)
async def _bad_value(request: Request, error: ValidationError):
    return _problem(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))


@app.exception_handler(crawler.CrawlError)
async def _crawl_failed(request: Request, error: crawler.CrawlError):
    return _problem(status.HTTP_502_BAD_GATEWAY, str(error))


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/", response_model=Home, tags=["start here"])
def home() -> Home:
    """What this project is, how to set it up, and every endpoint explained."""
    return help_text.home()


@app.get("/health", tags=["basics"])
def health(session: Session = Depends(get_session)) -> dict:
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        return {"status": "database unreachable", "version": APP_VERSION}
    return {"status": "ok", "version": APP_VERSION}


@app.get("/options", tags=["basics"])
def options() -> dict:
    """Every choice you can make, and the number each one turns into."""
    return all_options()


@app.post("/recommend", response_model=Result, tags=["the main one"])
def make_recommendation(
    answers: RecommendInput, session: Session = Depends(get_session)
) -> Result:
    """Send your answers, get the recommendation.

    Nothing is stored and nothing is crawled while you wait. It reads the
    catalog as it is right now and works the answer out.
    """
    available = catalog_loader.load(session, region=answers.region)
    return recommend(answers, available)


class RecommendHelp(EndpointHelp):
    existing_computer_fields: list[FieldHelp] = []


@app.get("/recommend", response_model=RecommendHelp, tags=["the main one"])
def what_to_send_to_recommend() -> RecommendHelp:
    """What to put in the body of POST /recommend, with an example you can copy."""
    return RecommendHelp(
        **help_text.recommend_help().model_dump(),
        existing_computer_fields=help_text.existing_computer_fields(),
    )


@app.get("/catalog", response_model=Catalog, tags=["see the data"])
def show_catalog(
    region: str | None = None, session: Session = Depends(get_session)
) -> Catalog:
    """The hardware, models and plans the recommendation is based on."""
    return catalog_loader.load(session, region=region)


class StoredPage(Strict):
    url: str
    fetched_at: str
    changed_last_time: bool
    rows_found: int
    characters: int


@app.get("/pages", response_model=list[StoredPage], tags=["see the data"])
def show_pages(session: Session = Depends(get_session)) -> list[StoredPage]:
    """What the crawler fetched, and how much of it it understood."""
    return [
        StoredPage(
            url=row.url,
            fetched_at=row.fetched_at.isoformat(),
            changed_last_time=row.changed,
            rows_found=row.rows_found,
            characters=len(row.markdown),
        )
        for row in session.scalars(select(Page).order_by(Page.url)).all()
    ]


class SourceIn(Strict):
    url: str
    label: str = ""


@app.get("/sources", tags=["see the data"])
def show_sources(session: Session = Depends(get_session)) -> list[dict]:
    return [
        {"url": row.url, "label": row.label, "enabled": row.enabled}
        for row in session.scalars(select(Source).order_by(Source.url)).all()
    ]


@app.post("/sources", status_code=status.HTTP_201_CREATED, tags=["see the data"])
def add_source(new: SourceIn, session: Session = Depends(get_session)) -> dict:
    """Register a page for the crawler. It is fetched on the next /crawl."""
    from app import netguard

    try:
        netguard.check_shape(new.url)
    except netguard.Blocked as blocked:
        return _problem(status.HTTP_422_UNPROCESSABLE_CONTENT, str(blocked))

    session.add(Source(url=new.url, label=new.label))
    session.flush()
    return {"url": new.url, "label": new.label, "enabled": True}


@app.get("/sources/help", response_model=EndpointHelp, tags=["see the data"])
def what_to_send_to_sources() -> EndpointHelp:
    """What to put in the body of POST /sources.

    The plain GET /sources is already taken by the list of registered sources,
    so the instructions live here.
    """
    return help_text.sources_help()


@app.get("/crawl", response_model=EndpointHelp, tags=["crawler"])
def what_crawl_does() -> EndpointHelp:
    """What POST /crawl does and what it gives back. It takes no body."""
    return help_text.crawl_help()


@app.post("/crawl", tags=["crawler"])
def run_crawler(session: Session = Depends(get_session)) -> dict:
    """Fetch every enabled source now and update the catalog from what comes back.

    This runs while you wait, because there are only a handful of sources. It
    returns exactly what it did with each one.
    """
    report = asyncio.run(crawler.crawl_all(session))
    return report.as_dict()
