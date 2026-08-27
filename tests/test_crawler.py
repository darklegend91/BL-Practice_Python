import asyncio
from types import SimpleNamespace

from crawler import crawler


class FakeCrawler:
    instances = []

    def __init__(self, config):
        self.config = config
        self.urls = []
        self.entered = False
        self.exited = False
        self.__class__.instances.append(self)

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True

    async def arun(self, url):
        self.urls.append(url)
        return SimpleNamespace(url=url, success=True)


def test_crawl_page_uses_one_browser_and_preserves_order(monkeypatch):
    FakeCrawler.instances.clear()
    monkeypatch.setattr(crawler, "AsyncWebCrawler", FakeCrawler)

    results = asyncio.run(crawler.crawl_page(["first", "second"]))

    instance = FakeCrawler.instances[0]
    assert instance.config is crawler.browser_config
    assert instance.entered and instance.exited
    assert instance.urls == ["first", "second"]
    assert [result.url for result in results] == ["first", "second"]


def test_save_to_file_writes_successes_and_failures(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "output" / "crawled.md"
    results = [
        SimpleNamespace(
            success=True,
            url="https://example.com/ok",
            markdown=SimpleNamespace(raw_markdown="GPU details"),
        ),
        SimpleNamespace(
            success=False,
            url="https://example.com/fail",
            error_message="browser failed",
        ),
    ]

    crawler.save_to_file(str(target), results)

    content = target.read_text(encoding="utf-8")
    assert content.startswith("# This is the crwaled Extracted Data")
    assert "## Source :\nhttps://example.com/ok" in content
    assert "GPU details" in content
    assert "Failed Url \nhttps://example.com/fail" in content
    assert "Error: \nbrowser failed" in content
