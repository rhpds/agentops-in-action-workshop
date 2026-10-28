"""Direct-HTTP web extract provider for the Northgate lab.

Hermes ships seven web backends and not one of them can fetch a URL in this
image: tavily, exa and parallel need SaaS credentials; searxng, brave-free and
ddgs are search-only; and firecrawl -- the only self-hostable one, via
FIRECRAWL_API_URL -- needs a ``firecrawl`` package that waterplant-hermes does
not install. So ``web_extract`` answers every call with "only supports search,
not direct URL content extraction", and the agent has no way to read a page.

That is not a missing nicety. Two attacks and one evaluation turn entirely on
the agent fetching a URL, and with no working fetch they can only ever report
"blocked" -- telling a participant they are defended against something that
was never tried.

This plugin is installed at ``$HERMES_HOME/plugins/web/firecrawl/`` so its
path-derived key collides with the bundled provider's; hermes_cli/plugins.py
dedups by key and lets the user source win, so the bundled module is never
imported and there is no registration race to lose.
"""

from __future__ import annotations


def register(ctx) -> None:
    """Register the direct-HTTP provider.

    The import is deferred into the function body for the reason hermes_otel
    documents: loading this file outside a package context would break a
    relative import at module scope.
    """
    from .provider_direct import DirectHTTPWebProvider

    ctx.register_web_search_provider(DirectHTTPWebProvider())
