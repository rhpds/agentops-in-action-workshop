"""A web_extract backend that just fetches the URL.

No extraction service, no API key: httpx.get, follow redirects, hand back the
body. That is all the lab needs, and it is the only option that works against
a cluster with no egress to a SaaS extraction API.

Two behaviours here are load-bearing for the lab rather than incidental:

* **Redirects are followed.** malicious-doc-redirect is the case where a
  legitimate documentation page 302s onward to an attacker path, and the
  lesson is that allowing the documentation *host* is not enough. A provider
  that refused redirects would defeat the attack inside the agent, where no
  participant can see or change the decision -- and would report the attack
  blocked when nothing had been configured.

* **The redirect chain is logged.** Every hop goes to this pod's log, and
  into ``metadata.redirect_chain`` / ``metadata.final_url`` on the result.
  Note that web_extract_tool's post-processing drops ``metadata`` before the
  model sees it -- verified on a running pod -- so the log is where the chain
  survives. That is a secondary record by design: the authoritative answer to
  "did the agent end up at the attacker path" is the documentation site's own
  hit log, because it is the receiving end rather than a claim made by the
  thing under test.

What this does NOT do is filter URLs, and that is deliberate. Restricting
egress is the participant's job, in policy they can see and change; an
allowlist here would move enforcement into a file nobody in the lab reads and
would report attacks as blocked by something they never configured.

Note that Hermes' own SSRF gate in tools/url_safety.py runs ahead of this and
would otherwise refuse every address in the namespace, which is why the chart
sets security.allow_private_urls for this agent. Cloud metadata endpoints stay
blocked there regardless of that flag.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

#: Per-URL budget. Short: a documentation fetch that takes longer than this has
#: been swallowed by something, and the probe harness has its own deadline.
TIMEOUT_S = float(os.environ.get("WEB_DIRECT_TIMEOUT_S", "20"))

#: Redirect budget. Non-zero because following one is the whole point; small
#: because a longer chain is a loop, not a document.
MAX_REDIRECTS = int(os.environ.get("WEB_DIRECT_MAX_REDIRECTS", "5"))

#: Cap on the body handed back to the model, per URL. An unbounded page would
#: spend the context window on boilerplate.
MAX_CHARS = int(os.environ.get("WEB_DIRECT_MAX_CHARS", "20000"))

_UA = "waterplant-maintenance-assistant/1.0 (Hermes web_extract)"


class DirectHTTPWebProvider(WebSearchProvider):
    """Fetch URLs over plain HTTP(S)."""

    @property
    def name(self) -> str:
        """``firecrawl`` -- not a descriptive name, and not by preference.

        tools/web_tools.py resolves the configured backend through
        ``_is_backend_available()``, a hardcoded if-chain over the seven
        bundled names that returns False for anything else. A provider named
        ``direct`` is therefore never selectable: the lookup falls back to
        ddgs, finds a search-only provider, and returns "X is a search-only
        backend" without ever consulting the registry's own resolution.

        Taking the bundled name is what makes ``web.extract_backend:
        firecrawl`` route here. ``display_name`` carries the honest label, so
        ``hermes plugins list`` and ``hermes tools`` still say what this is.
        """
        return "firecrawl"

    @property
    def display_name(self) -> str:
        return "Direct HTTP (Northgate lab)"

    def is_available(self) -> bool:
        """Always. There is no credential to be missing."""
        return True

    def supports_search(self) -> bool:
        """No.

        Leaving this False keeps web_search on ddgs, which works. Note that
        setting FIRECRAWL_API_URL makes the legacy ``_get_backend()`` walk
        pick "firecrawl" for *search* too, so seed-config pins
        ``web.search_backend: ddgs`` explicitly -- without it web_search
        resolves here and fails as extract-only.
        """
        return False

    def supports_extract(self) -> bool:
        return True

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Fetch each URL. Sync -- the dispatcher runs this in a thread."""
        import httpx

        results: List[Dict[str, Any]] = []
        for url in urls:
            results.append(self._fetch_one(httpx, url))
        return results

    def _fetch_one(self, httpx: Any, url: str) -> Dict[str, Any]:
        try:
            with httpx.Client(
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
                timeout=TIMEOUT_S,
                headers={"User-Agent": _UA},
            ) as client:
                response = client.get(url)
        except Exception as exc:  # noqa: BLE001 - one bad URL must not sink the batch
            logger.info("web_extract: %s failed: %s", url, exc)
            return {
                "url": url, "title": "", "content": "", "raw_content": "",
                "error": f"{type(exc).__name__}: {exc}",
            }

        chain = [str(r.url) for r in response.history]
        final_url = str(response.url)
        body = response.text or ""
        truncated = len(body) > MAX_CHARS
        content = body[:MAX_CHARS]

        if chain:
            logger.info("web_extract: %s -> %s", url, " -> ".join(chain + [final_url]))

        return {
            "url": url,
            "title": _title_of(body) or final_url,
            "content": content,
            "raw_content": content,
            "metadata": {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "final_url": final_url,
                # Empty on a direct hit. Populated, this is the evidence that
                # the agent was walked somewhere it was not asked to go.
                "redirect_chain": chain,
                "truncated": truncated,
            },
        }


def _title_of(body: str) -> str:
    """The <title>, if the response looks like HTML. Cheap and tolerant."""
    lowered = body.lower()
    start = lowered.find("<title")
    if start == -1:
        return ""
    start = lowered.find(">", start)
    end = lowered.find("</title>", start)
    if start == -1 or end == -1:
        return ""
    return body[start + 1:end].strip()[:200]
