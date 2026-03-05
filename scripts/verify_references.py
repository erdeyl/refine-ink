#!/usr/bin/env python3
"""
Verify academic paper references using free APIs (CrossRef, OpenAlex, Semantic Scholar).

Three-tier verification cascade with fuzzy title matching, DOI resolution,
and proper rate limiting with exponential backoff.

Usage:
    python verify_references.py references.json --email user@example.com [--s2-api-key KEY]
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CROSSREF_BASE = "https://api.crossref.org/works"
OPENALEX_BASE = "https://api.openalex.org/works"
S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"

TITLE_MATCH_VERIFIED = 0.85
TITLE_MATCH_REVIEW = 0.70

DOI_REGEX = re.compile(r"^10\.\d{4,9}/[^\s]+$")

MAX_RETRIES = 4
INITIAL_BACKOFF = 1.0  # seconds

# Rate-limit windows (requests per second)
CROSSREF_RPS = 10
OPENALEX_RPS = 10
S2_RPS = 5  # conservative for unauthenticated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for comparison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_similarity(a: str, b: str) -> float:
    """Return 0-1 similarity between two titles using SequenceMatcher."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def is_valid_doi(doi: str) -> bool:
    return bool(doi and DOI_REGEX.match(doi.strip()))


def normalize_doi_value(doi: str) -> str:
    """Canonical DOI normalization for equality checks."""
    if not doi:
        return ""
    value = doi.strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    return value.strip()


def extract_year(value: object) -> Optional[str]:
    """Extract a 4-digit year from API values."""
    if value is None:
        return None
    if isinstance(value, int):
        if 1800 <= value <= 2100:
            return str(value)
        return None
    if isinstance(value, str):
        m = re.search(r"\b(18|19|20)\d{2}\b", value)
        return m.group(0) if m else None
    return None


def extract_crossref_year(record: dict) -> Optional[str]:
    """Extract publication year from a CrossRef work/item."""
    for key in ("issued", "published-print", "published-online", "created"):
        parts = record.get(key, {}).get("date-parts", [])
        if parts and isinstance(parts[0], list) and parts[0]:
            year = extract_year(parts[0][0])
            if year:
                return year
    return None


@dataclass
class MatchResult:
    """Result from a single API lookup."""
    found: bool = False
    source: Optional[str] = None
    title: Optional[str] = None
    doi: Optional[str] = None
    similarity: float = 0.0
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Token-bucket style async rate limiter."""

    def __init__(self, rps: float):
        self._interval = 1.0 / rps
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


# ---------------------------------------------------------------------------
# HTTP helper with retries + backoff
# ---------------------------------------------------------------------------


async def request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    limiter: RateLimiter,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> Optional[httpx.Response]:
    """Make an HTTP request with rate limiting and exponential backoff."""
    backoff = INITIAL_BACKOFF
    for attempt in range(MAX_RETRIES):
        await limiter.acquire()
        try:
            resp = await client.request(method, url, params=params, headers=headers, timeout=30.0)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                # Retry with backoff
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            # Other client errors: don't retry
            return None
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            await asyncio.sleep(backoff)
            backoff *= 2
            continue
    return None


# ---------------------------------------------------------------------------
# CrossRef
# ---------------------------------------------------------------------------


async def crossref_lookup(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    ref: dict,
    mailto: Optional[str],
) -> MatchResult:
    """Search CrossRef by DOI (if available) then by bibliographic query."""
    result = MatchResult()

    # --- Try DOI first ---
    doi = (ref.get("doi") or "").strip()
    if is_valid_doi(doi):
        params = {}
        if mailto:
            params["mailto"] = mailto
        url = f"{CROSSREF_BASE}/{doi}"
        resp = await request_with_backoff(client, "GET", url, limiter, params=params or None)
        if resp is not None:
            try:
                data = resp.json()
                work = data.get("message", {})
                matched_title = ""
                titles = work.get("title", [])
                if titles:
                    matched_title = titles[0]
                result.found = True
                result.source = "crossref"
                result.title = matched_title
                result.doi = work.get("DOI", doi)
                year = extract_crossref_year(work)
                if year:
                    result.extra["year"] = year
                ref_title = ref.get("title", "")
                if ref_title and matched_title:
                    result.similarity = title_similarity(ref_title, matched_title)
                else:
                    result.similarity = 1.0  # DOI matched directly
                return result
            except (json.JSONDecodeError, KeyError):
                pass

    # --- Bibliographic search ---
    ref_title = ref.get("title", "")
    if not ref_title:
        return result

    params = {"rows": 5}
    if mailto:
        params["mailto"] = mailto

    # Build bibliographic query
    query_parts = [ref_title]
    authors = ref.get("authors")
    if authors:
        if isinstance(authors, list):
            query_parts.extend(authors[:2])
        else:
            query_parts.append(str(authors))
    params["query.bibliographic"] = " ".join(query_parts)

    resp = await request_with_backoff(client, "GET", CROSSREF_BASE, limiter, params=params)
    if resp is None:
        return result

    try:
        data = resp.json()
        items = data.get("message", {}).get("items", [])
    except (json.JSONDecodeError, KeyError):
        return result

    best_sim = 0.0
    best_item = None
    for item in items:
        titles = item.get("title", [])
        if not titles:
            continue
        candidate = titles[0]
        sim = title_similarity(ref_title, candidate)
        if sim > best_sim:
            best_sim = sim
            best_item = item

    if best_item and best_sim >= TITLE_MATCH_REVIEW:
        result.found = True
        result.source = "crossref"
        result.title = best_item.get("title", [""])[0]
        result.doi = best_item.get("DOI")
        result.similarity = best_sim
        year = extract_crossref_year(best_item)
        if year:
            result.extra["year"] = year

    return result


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------


async def openalex_lookup(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    ref: dict,
    mailto: Optional[str],
) -> MatchResult:
    """Search OpenAlex by DOI or title."""
    result = MatchResult()

    # --- DOI lookup ---
    doi = (ref.get("doi") or "").strip()
    if is_valid_doi(doi):
        params = {}
        if mailto:
            params["mailto"] = mailto
        url = f"{OPENALEX_BASE}/doi:{doi}"
        resp = await request_with_backoff(client, "GET", url, limiter, params=params or None)
        if resp is not None:
            try:
                data = resp.json()
                matched_title = data.get("title", "")
                result.found = True
                result.source = "openalex"
                result.title = matched_title
                result.doi = doi
                year = extract_year(data.get("publication_year"))
                if year:
                    result.extra["year"] = year
                ref_title = ref.get("title", "")
                if ref_title and matched_title:
                    result.similarity = title_similarity(ref_title, matched_title)
                else:
                    result.similarity = 1.0
                return result
            except (json.JSONDecodeError, KeyError):
                pass

    # --- Title search ---
    ref_title = ref.get("title", "")
    if not ref_title:
        return result

    params = {
        "filter": f"title.search:{ref_title}",
        "per_page": 5,
    }
    if mailto:
        params["mailto"] = mailto

    resp = await request_with_backoff(client, "GET", OPENALEX_BASE, limiter, params=params)
    if resp is None:
        return result

    try:
        data = resp.json()
        items = data.get("results", [])
    except (json.JSONDecodeError, KeyError):
        return result

    best_sim = 0.0
    best_item = None
    for item in items:
        candidate = item.get("title", "")
        if not candidate:
            continue
        sim = title_similarity(ref_title, candidate)
        if sim > best_sim:
            best_sim = sim
            best_item = item

    if best_item and best_sim >= TITLE_MATCH_REVIEW:
        result.found = True
        result.source = "openalex"
        result.title = best_item.get("title", "")
        result.doi = best_item.get("doi", "")
        if result.doi and result.doi.startswith("https://doi.org/"):
            result.doi = result.doi.replace("https://doi.org/", "")
        result.similarity = best_sim
        year = extract_year(best_item.get("publication_year"))
        if year:
            result.extra["year"] = year

    return result


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------


async def s2_lookup(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    ref: dict,
    api_key: Optional[str],
) -> MatchResult:
    """Search Semantic Scholar by title."""
    result = MatchResult()

    ref_title = ref.get("title", "")

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    # --- DOI lookup first ---
    doi = (ref.get("doi") or "").strip()
    if is_valid_doi(doi):
        url = f"{S2_BASE}/DOI:{doi}"
        params = {"fields": "title,year,externalIds"}
        resp = await request_with_backoff(
            client, "GET", url, limiter, params=params, headers=headers or None
        )
        if resp is not None:
            try:
                data = resp.json()
                matched_title = data.get("title", "")
                result.found = True
                result.source = "semantic_scholar"
                result.title = matched_title
                ext_ids = data.get("externalIds", {})
                result.doi = ext_ids.get("DOI", doi)
                year = extract_year(data.get("year"))
                if year:
                    result.extra["year"] = year
                if ref_title and matched_title:
                    result.similarity = title_similarity(ref_title, matched_title)
                else:
                    result.similarity = 1.0
                return result
            except (json.JSONDecodeError, KeyError):
                pass

    # --- Title search ---
    if not ref_title:
        return result

    url = f"{S2_BASE}/search"
    params = {"query": ref_title, "limit": 5, "fields": "title,year,externalIds"}
    resp = await request_with_backoff(
        client, "GET", url, limiter, params=params, headers=headers or None
    )
    if resp is None:
        return result

    try:
        data = resp.json()
        items = data.get("data", [])
    except (json.JSONDecodeError, KeyError):
        return result

    if not items:
        return result

    best_sim = 0.0
    best_item = None
    for item in items:
        candidate = item.get("title", "")
        if not candidate:
            continue
        sim = title_similarity(ref_title, candidate)
        if sim > best_sim:
            best_sim = sim
            best_item = item

    if best_item and best_sim >= TITLE_MATCH_REVIEW:
        result.found = True
        result.source = "semantic_scholar"
        result.title = best_item.get("title", "")
        ext_ids = best_item.get("externalIds", {})
        result.doi = ext_ids.get("DOI")
        result.similarity = best_sim
        year = extract_year(best_item.get("year"))
        if year:
            result.extra["year"] = year

    return result


# ---------------------------------------------------------------------------
# Suspicion analysis
# ---------------------------------------------------------------------------


def detect_suspicion(ref: dict, match: MatchResult) -> list[str]:
    """Detect suspicious patterns even in unverifiable references."""
    reasons = []

    doi = (ref.get("doi") or "").strip()
    title = ref.get("title", "")

    # Valid DOI format but couldn't resolve
    if is_valid_doi(doi) and not match.found:
        reasons.append("DOI format is valid but does not resolve in any API")

    # Title looks plausible (long enough, has words) but not found
    if title and len(title.split()) >= 4 and not match.found:
        reasons.append("Title appears plausible but was not found in any database")

    # Partial match (found but low similarity)
    if match.found and match.similarity < TITLE_MATCH_VERIFIED:
        reasons.append(
            f"Title similarity is only {match.similarity:.0%}, below verification threshold"
        )

    # Journal name check (simple heuristic)
    journal = ref.get("journal", "")
    if journal and not match.found:
        reasons.append(f"Journal '{journal}' could not be confirmed via CrossRef")

    # Year mismatch check
    year = ref.get("year")
    if year and match.found and match.extra.get("year"):
        if str(year) != str(match.extra.get("year")):
            reasons.append(
                f"Year mismatch: reference says {year}, API returned {match.extra['year']}"
            )

    return reasons


# ---------------------------------------------------------------------------
# Single-reference verification
# ---------------------------------------------------------------------------


async def verify_one(
    idx: int,
    ref: dict,
    client: httpx.AsyncClient,
    cr_limiter: RateLimiter,
    oa_limiter: RateLimiter,
    s2_limiter: RateLimiter,
    mailto: Optional[str],
    s2_api_key: Optional[str],
) -> dict:
    """Run the three-tier cascade for one reference."""

    raw_text = ref.get("raw_text", "")

    # --- Tier 1: CrossRef ---
    match = await crossref_lookup(client, cr_limiter, ref, mailto)
    if match.found and match.similarity >= TITLE_MATCH_VERIFIED:
        return _build_output(idx, ref, match, raw_text)

    # Keep the best partial match so far
    best = match

    # --- Tier 2: OpenAlex ---
    match = await openalex_lookup(client, oa_limiter, ref, mailto)
    if match.found and match.similarity >= TITLE_MATCH_VERIFIED:
        return _build_output(idx, ref, match, raw_text)
    if match.found and match.similarity > best.similarity:
        best = match

    # --- Tier 3: Semantic Scholar ---
    match = await s2_lookup(client, s2_limiter, ref, s2_api_key)
    if match.found and match.similarity >= TITLE_MATCH_VERIFIED:
        return _build_output(idx, ref, match, raw_text)
    if match.found and match.similarity > best.similarity:
        best = match

    # --- Cascade exhausted ---
    return _build_output(idx, ref, best, raw_text)


def _build_output(idx: int, ref: dict, match: MatchResult, raw_text: str) -> dict:
    """Construct the output dict from a MatchResult."""
    doi = (ref.get("doi") or "").strip()
    ref_title = ref.get("title", "")
    exact_doi_match = bool(
        doi
        and match.doi
        and normalize_doi_value(doi) == normalize_doi_value(match.doi)
    )

    # Determine confidence and status
    if match.found:
        # Exact DOI match is strong evidence, but large metadata mismatch still needs review.
        if exact_doi_match:
            if ref_title and match.title and match.similarity < TITLE_MATCH_REVIEW:
                confidence = 60
                status = "suspicious"
                details = (
                    f"DOI resolves exactly, but title similarity is only {match.similarity:.0%} "
                    "(possible extraction/metadata mismatch)"
                )
            elif ref_title and match.title and match.similarity < TITLE_MATCH_VERIFIED:
                confidence = 75
                status = "suspicious"
                details = (
                    f"DOI resolves exactly, but title similarity is {match.similarity:.0%} "
                    "(below verification threshold)"
                )
            else:
                confidence = 100
                status = "verified"
                details = "Exact DOI match confirmed"
        elif match.similarity >= TITLE_MATCH_VERIFIED:
            confidence = 90
            status = "verified"
            details = f"Title match {match.similarity:.0%} (above {TITLE_MATCH_VERIFIED:.0%} threshold)"
        elif match.similarity >= TITLE_MATCH_REVIEW:
            confidence = 70
            status = "suspicious"
            details = (
                f"Title match {match.similarity:.0%} "
                f"(between {TITLE_MATCH_REVIEW:.0%} and {TITLE_MATCH_VERIFIED:.0%}; needs review)"
            )
        else:
            confidence = 0
            status = "unverifiable"
            details = "Best match similarity too low"
    else:
        confidence = 0
        status = "unverifiable"
        details = "Not found in CrossRef, OpenAlex, or Semantic Scholar"

    suspicion_reasons = detect_suspicion(ref, match)
    suspicion_confidence: Optional[int] = None
    if suspicion_reasons and status == "verified":
        status = "suspicious"
        confidence = min(confidence, 80)
        details = f"{details}; metadata inconsistencies require review"
    elif suspicion_reasons and status == "unverifiable":
        status = "suspicious"
        # Keep confidence semantics as "verification confidence" (still 0 here)
        # and report suspicion strength separately to avoid ambiguity.
        suspicion_confidence = 40
        details = f"{details}; heuristic signals indicate potential fabrication"

    out = {
        "ref_index": idx,
        "raw_text": raw_text or _reconstruct_raw(ref),
        "status": status,
        "verified_by": match.source if match.found and confidence > 70 else None,
        "confidence": confidence,
        "matched_title": match.title or "",
        "matched_doi": match.doi or "",
        "details": details,
    }
    if suspicion_confidence is not None:
        out["suspicion_confidence"] = suspicion_confidence
    if suspicion_reasons:
        out["suspicion_reasons"] = suspicion_reasons
    return out


def _reconstruct_raw(ref: dict) -> str:
    """Build a raw_text fallback from structured fields."""
    parts = []
    if ref.get("authors"):
        a = ref["authors"]
        parts.append(", ".join(a) if isinstance(a, list) else str(a))
    if ref.get("year"):
        parts.append(f"({ref['year']})")
    if ref.get("title"):
        parts.append(ref["title"])
    if ref.get("journal"):
        parts.append(ref["journal"])
    if ref.get("doi"):
        parts.append(f"doi:{ref['doi']}")
    return ". ".join(parts)


# ---------------------------------------------------------------------------
# Batch orchestration
# ---------------------------------------------------------------------------

# Semaphore to limit concurrency (avoid overwhelming APIs)
MAX_CONCURRENT = 5


async def verify_all(
    references: list[dict],
    mailto: Optional[str],
    s2_api_key: Optional[str],
) -> list[dict]:
    """Verify all references with bounded concurrency."""

    cr_limiter = RateLimiter(CROSSREF_RPS)
    oa_limiter = RateLimiter(OPENALEX_RPS)
    s2_limiter = RateLimiter(S2_RPS)

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results: list[Optional[dict]] = [None] * len(references)
    total = len(references)

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "VerifyReferences/1.0 (academic-tool)"},
    ) as client:

        async def _worker(idx: int, ref: dict):
            async with sem:
                print(f"Verifying reference {idx + 1}/{total}...", flush=True)
                results[idx] = await verify_one(
                    idx, ref, client, cr_limiter, oa_limiter, s2_limiter, mailto, s2_api_key
                )

        tasks = [asyncio.create_task(_worker(i, ref)) for i, ref in enumerate(references)]
        await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_summary(results: list[dict]):
    """Print a human-readable summary to stdout."""
    total = len(results)
    verified = sum(1 for r in results if r["status"] == "verified")
    suspicious = sum(1 for r in results if r["status"] == "suspicious")
    unverifiable = sum(1 for r in results if r["status"] == "unverifiable")

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"  Total references : {total}")
    print(f"  Verified         : {verified}")
    print(f"  Suspicious       : {suspicious}")
    print(f"  Unverifiable     : {unverifiable}")
    print("=" * 60)

    if suspicious > 0:
        print("\nSUSPICIOUS REFERENCES:")
        for r in results:
            if r["status"] == "suspicious":
                print(f"  [{r['ref_index']}] {r['raw_text'][:100]}")
                if r.get("suspicion_reasons"):
                    for reason in r["suspicion_reasons"]:
                        print(f"       - {reason}")
                print(f"       Confidence: {r['confidence']}%  Details: {r['details']}")

    if unverifiable > 0:
        print("\nUNVERIFIABLE REFERENCES:")
        for r in results:
            if r["status"] == "unverifiable":
                print(f"  [{r['ref_index']}] {r['raw_text'][:100]}")
                if r.get("suspicion_reasons"):
                    for reason in r["suspicion_reasons"]:
                        print(f"       - {reason}")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify academic references against CrossRef, OpenAlex, and Semantic Scholar."
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to JSON file containing an array of reference objects.",
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Email for CrossRef/OpenAlex polite pool (strongly recommended).",
    )
    parser.add_argument(
        "--s2-api-key",
        type=str,
        default=None,
        help="Semantic Scholar API key (or set S2_API_KEY env var).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path. Defaults to <input_name>_verified.json.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        references = json.load(f)

    if not isinstance(references, list):
        print("Error: input JSON must be an array of reference objects.", file=sys.stderr)
        sys.exit(1)

    if not references:
        print("No references to verify.")
        sys.exit(0)

    # Resolve API key
    s2_api_key = args.s2_api_key or os.environ.get("S2_API_KEY")

    mailto = args.email
    if not mailto:
        print(
            "Warning: --email not provided. API requests will not use polite pool "
            "and may be rate-limited more aggressively.",
            file=sys.stderr,
        )

    # Run verification
    print(f"Loaded {len(references)} references from {input_path.name}")
    results = asyncio.run(verify_all(references, mailto, s2_api_key))

    # Write output
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(f"{input_path.stem}_verified.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nFull report written to: {output_path}")

    # Summary
    print_summary(results)


if __name__ == "__main__":
    main()
