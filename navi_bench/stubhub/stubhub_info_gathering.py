from typing import TypedDict
from pydantic import BaseModel
from playwright.async_api import Page
from beartype import beartype
from loguru import logger
import functools
import itertools

from navi_bench.base import BaseMetric

class MultiCandidateQuery(TypedDict, total=False):
    event_names: list[str] | None
    dates: list[str] | None              # YYYY-MM-DD
    venues: list[str] | None
    ticket_quantities: list[int] | None
    min_price: float | None              # per-ticket
    max_price: float | None              # per-ticket
    domain: list[str] | None             # sports | concerts | theatre | festivals

class SingleCandidateQuery(TypedDict, total=False):
    event_name: str | None
    date: str | None
    venue: str | None
    ticket_quantity: int | None
    min_price: float | None
    max_price: float | None

class InfoDict(TypedDict, total=False):
    url: str
    eventName: str
    eventDate: str
    venue: str
    domain: str

    ticketQuantity: int
    price: float

    availability: str   # "available" | "sold_out"
    info: str           # raw UI text

class FinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[MultiCandidateQuery]]
    is_query_covered: list[bool]

@beartype
class StubHubInfoGathering(BaseMetric):
    """
    Gather ticket availability information from StubHub
    to evaluate query coverage.
    """

    def __init__(self, queries: list[list[MultiCandidateQuery]]) -> None:
        super().__init__()
        self.queries = queries

        self._all_infos: list[list[InfoDict]] = []
        self._is_query_covered: list[bool] = [False] * len(queries)

        # For proving unavailability (same idea as OpenTable)
        self._unavailable_evidences: list[list[list[InfoDict]]] = [
            [[] for _ in alternatives] for alternatives in queries
        ]

    @functools.cached_property
    def js_script(self) -> str:
        from pathlib import Path
        with open(Path(__file__).parent / "stubhub_info_gathering.js", "r", encoding="utf-8") as f:
            return f.read()

    async def reset(self) -> None:
        self._all_infos = []
        self._is_query_covered = [False] * len(self.queries)
        self._unavailable_evidences = [
            [[] for _ in alternatives] for alternatives in self.queries
        ]

    async def update(self, **kwargs) -> None:
        page: Page = kwargs["page"]

        # NEWNEWNEWN
        # 1. Read page URL first
        url = page.url

        # 2. Only wait for ticket listings on EVENT pages
        if "/event/" in url:
            try:
                await page.wait_for_selector(
                    '[aria-label*="ticket"], [data-testid*="listing"]',
                    timeout=15000
                )

            except Exception:
                logger.info("StubHub: no ticket listings found on event page yet")
        #######

        if "/secure/Search" in page.url:
            await page.wait_for_selector(
                '[data-testid="primaryGrid"] li[data-expanded]',
                timeout=15000
            )

        infos: list[InfoDict] = await page.evaluate(self.js_script)
        logger.info(f"StubHub gathered {len(infos)} infos")
        logger.info(f"{infos}")

        self._all_infos.append(infos)

        for i, alternative_conditions in enumerate(self.queries):
            if self._is_query_covered[i]:
                continue

            for info in infos:
                if self._check_alternative_conditions(
                    i, alternative_conditions, info
                ):
                    logger.info(
                        f"StubHub query {i} covered by info={info}"
                    )
                    self._is_query_covered[i] = True
                    break

    def _check_alternative_conditions(
        self,
        i: int,
        alternative_conditions: list[MultiCandidateQuery],
        info: InfoDict,
    ) -> bool:
        for j, query in enumerate(alternative_conditions):
            evidences = self._unavailable_evidences[i][j]
            if self._check_multi_candidate_query(query, info, evidences):
                return True
        return False

    @classmethod
    def _check_multi_candidate_query(
        cls,
        query: MultiCandidateQuery,
        info: InfoDict,
        evidences: list[InfoDict],
    ) -> bool:
        # Event name
        if names := query.get("event_names"):
            info_name = info.get("eventName")
            if info_name is not None:
                if not any(
                    name.lower() in info_name.lower()
                    for name in names
                ):
                    return False

        # Domain
        if domains := query.get("domain"):
            if info.get("domain") not in domains:
                return False

        # Date
        if dates := query.get("dates"):
            if info.get("eventDate") not in dates:
                return False

        # Venue
        if venues := query.get("venues"):
            if not any(
                venue.lower() in info.get("venue", "").lower()
                for venue in venues
            ):
                return False

        # Ticket quantity
        if quantities := query.get("ticket_quantities"):
            if info.get("ticketQuantity", 0) < min(quantities):
                return False

        # Price (per-ticket)
        price = info.get("price")
        if price is not None:
            if query.get("min_price") is not None and price < query["min_price"]:
                return False
            if query.get("max_price") is not None and price > query["max_price"]:
                return False

        # Availability semantics
        availability = info.get("availability", "").lower()

        if availability == "sold_out":
            evidences.append(info)
            return False   # covered later via exhaustion

        if availability == "available":
            return True

        return False


    async def compute(self) -> FinalResult:
        for i, alternatives in enumerate(self.queries):
            if self._is_query_covered[i]:
                continue

            for j, query in enumerate(alternatives):
                if not self._is_exhausted(query, self._unavailable_evidences[i][j]):
                    break
            else:
                self._is_query_covered[i] = True

        n_queries = len(self.queries)
        n_covered = sum(self._is_query_covered)

        return FinalResult(
            score=n_covered / max(1, n_queries),
            n_queries=n_queries,
            n_covered=n_covered,
            queries=self.queries,
            is_query_covered=self._is_query_covered,
        )

    @classmethod
    def _is_exhausted(
        cls,
        query: MultiCandidateQuery,
        evidences: list[InfoDict],
    ) -> bool:
        names = query.get("event_names") or [None]
        dates = query.get("dates") or [None]
        venues = query.get("venues") or [None]
        quantities = query.get("ticket_quantities") or [None]

        for name, date, venue, qty in itertools.product(
            names, dates, venues, quantities
        ):
            found = False
            for info in evidences:
                if cls._check_single_candidate_query(
                    {
                        "event_name": name,
                        "date": date,
                        "venue": venue,
                        "ticket_quantity": qty,
                        "min_price": query.get("min_price"),
                        "max_price": query.get("max_price"),
                    },
                    info,
                ):
                    found = True
                    break

            if not found:
                return False

        return True

    @classmethod
    def _check_single_candidate_query(
        cls,
        query: SingleCandidateQuery,
        info: InfoDict,
    ) -> bool:
        if query.get("event_name"):
            info_name = info.get("eventName")
            if info_name is not None:
                if query["event_name"].lower() not in info_name.lower():
                    return False

        if query.get("date"):
            if info.get("eventDate") != query["date"]:
                return False

        if query.get("venue"):
            if query["venue"].lower() not in info.get("venue", "").lower():
                return False

        if query.get("ticket_quantity") is not None:
            if info.get("ticketQuantity", 0) < query["ticket_quantity"]:
                return False

        price = info.get("price")
        if price is not None:
            if query.get("min_price") is not None and price < query["min_price"]:
                return False
            if query.get("max_price") is not None and price > query["max_price"]:
                return False

        return info.get("availability") == "sold_out"

