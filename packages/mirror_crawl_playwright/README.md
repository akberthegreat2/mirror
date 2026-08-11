# mirror-crawl-playwright

A Mirror Crawl provider that drives a real Playwright browser (Chromium,
Firefox, or WebKit) to crawl sites — including JavaScript-rendered pages.

It is one of the three industry-grade crawl providers (local, scrapy,
playwright) that saturate the `crawl` capability (ADR-0046).

## Usage

```python
from mirror_crawl.models import CrawlRequest
from mirror_crawl_playwright.provider import PlaywrightCrawlProvider

provider = PlaywrightCrawlProvider()  # or PlaywrightCrawlProvider(settings=...)
await provider.setup()
result = await provider.crawl(CrawlRequest(url="https://example.com", max_pages=10))
await provider.teardown()
```

Set `headless=False` in `PlaywrightCrawlSettings` for a visible browser, and
`browser="firefox"` or `"webkit"` to switch engines.
