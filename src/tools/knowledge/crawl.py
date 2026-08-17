from __future__ import annotations

from pathlib import Path
from time import time
from urllib.parse import urlsplit
import asyncio
import uuid

from browser_executor import Crawl4AISession
from web import accept_observation, finalize_session, start_session, validate_capture


_UTILITY_SEGMENTS = {"account", "careers", "events", "jobs", "legal", "login", "privacy", "terms"}


def prioritize_links(requested_url: str, links) -> list[str]:
    requested_parts = [part for part in urlsplit(requested_url).path.split("/") if part]
    parent = requested_parts[:-1]

    def score(item):
        parts = [part.lower() for part in urlsplit(item).path.split("/") if part]
        shared = 0
        for left, right in zip(parent, parts):
            if left.lower() != right:
                break
            shared += 1
        utility = any(part in _UTILITY_SEGMENTS for part in parts)
        return (-shared, utility)

    return sorted(dict.fromkeys(links), key=score)


async def _trusted_crawl(root_url, policy, runtime_root: Path, scope: str, resolver=None, allow_private: bool = False) -> dict:
    session = start_session(root_url, policy, scope, resolver=resolver) if resolver else start_session(root_url, policy, scope)
    artifacts = runtime_root / session["session_id"]
    frontier, seen, pages, parent = [session["root_url"]], set(), [], None
    async with Crawl4AISession(session, artifacts, resolver, allow_private) as browser:
        while frontier:
            if time() >= session["deadline"]: break
            url = frontier.pop(0); route = urlsplit(url)._replace(fragment="").geturl()
            if route in seen: continue
            event_id = "evt-" + uuid.uuid4().hex[:12]
            captured = await browser.capture(url, event_id, parent)
            if time() >= session["deadline"]: raise ValueError("crawl exceeded wall-clock budget")
            session = accept_observation(session, captured.event, resolver=resolver) if resolver else accept_observation(session, captured.event)
            pages.append(captured.page); seen.add(route); parent = event_id
            if scope == "site":
                for link in prioritize_links(url, captured.actionable_links):
                    candidate = urlsplit(link)._replace(fragment="").geturl()
                    if candidate not in seen and candidate not in frontier: frontier.append(candidate)
            if session["no_progress_count"] >= policy.crawl_budget.consecutive_no_progress: break
    stop = "frontier_exhausted" if not frontier else "novelty_converged"
    report = finalize_session(session, stop, frontier)
    capture={"session_id":session["session_id"],"generation":"gen-"+uuid.uuid4().hex[:16],"pages":pages}
    validated=validate_capture(report,capture,runtime_root,resolver=resolver) if resolver else validate_capture(report,capture,runtime_root)
    return {"session":session,"validated":validated,"artifacts":str(artifacts),"status":"captured"}


def trusted_crawl(root_url, policy, runtime_root: Path, scope: str, resolver=None, allow_private: bool = False) -> dict:
    return asyncio.run(_trusted_crawl(root_url, policy, runtime_root, scope, resolver, allow_private))
