from app.odata.client import ODataClient, ODataSource, nav_page_is_last, nav_page_key


class _FakeResp:
    def __init__(self, value: list[dict]) -> None:
        self.status_code = 200
        self._value = value

    def json(self) -> dict:
        return {"value": self._value}

    def raise_for_status(self) -> None:
        return None


class _FakeHttp:
    def __init__(self, pages: list[list[dict]]) -> None:
        self.pages = pages
        self.calls: list[dict] = []

    def get(self, path: str, params: dict | None = None):
        self.calls.append(dict(params or {}))
        idx = len(self.calls) - 1
        value = self.pages[idx] if idx < len(self.pages) else []
        return _FakeResp(value)


def _client(pages: list[list[dict]]) -> tuple[ODataClient, _FakeHttp]:
    source = ODataSource(source_id="t", base_url="http://example/", username="u", password="p")
    client = ODataClient(source)
    client._client.close()
    fake = _FakeHttp(pages)
    client._client = fake  # type: ignore[method-assign]
    return client, fake


def test_nav_page_is_last_when_server_ignores_top():
    rows = [{"LineNumber": i} for i in range(1, 983)]
    assert nav_page_is_last(rows, top=200) is True
    assert nav_page_is_last(rows[:200], top=200) is False
    assert nav_page_is_last(rows[:50], top=200) is True
    assert nav_page_key(rows) == (1, 982, 982, None)


def test_iter_nav_stops_when_1c_dumps_whole_table():
    rows = [{"LineNumber": i} for i in range(1, 983)]
    client, fake = _client([rows, rows])
    got = list(client.iter_nav_collection("Document_X", "ref-1", top=200, max_pages=100))
    assert [row["LineNumber"] for row in got] == list(range(1, 983))
    assert len(fake.calls) == 1


def test_iter_nav_pages_when_top_and_skip_work():
    page1 = [{"LineNumber": i} for i in range(1, 201)]
    page2 = [{"LineNumber": i} for i in range(201, 351)]
    client, fake = _client([page1, page2])
    got = list(client.iter_nav_collection("Document_X", "ref-1", top=200, max_pages=100))
    assert [row["LineNumber"] for row in got] == list(range(1, 351))
    assert len(fake.calls) == 2
    assert fake.calls[1].get("$skip") == 200


def test_iter_nav_stops_on_repeated_page():
    page = [{"LineNumber": i} for i in range(1, 201)]
    client, fake = _client([page, page])
    got = list(client.iter_nav_collection("Document_X", "ref-1", top=200, max_pages=100))
    assert len(got) == 200
    assert len(fake.calls) == 2
