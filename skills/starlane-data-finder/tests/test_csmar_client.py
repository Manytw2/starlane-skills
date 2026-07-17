from __future__ import annotations

import json

import pytest

from scripts.csmar_client import CsmarClient, CsmarError, CsmarQuery


class Response:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.status = status
        self.data = json.dumps(payload).encode()


class Http:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> Response:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_list_databases_logs_in_and_uses_token() -> None:
    http = Http([Response({"code": 0, "data": {"token": "token-1"}}), Response({"code": 0, "data": ["财务报表"]})])
    client = CsmarClient("account", "password", http=http)

    assert client.list_databases() == ["财务报表"]
    assert http.calls[1][2]["headers"] == {"Lang": "0", "Token": "token-1", "belong": "0"}


def test_query_payload_keeps_dates_and_condition() -> None:
    query = CsmarQuery("FS_Combas", ["Stkcd"], "Stkcd='000001'", "2020-01-01", "2020-12-31")

    assert query.payload() == {"table": "FS_Combas", "columns": ["Stkcd"], "condition": "Stkcd='000001'", "startTime": "2020-01-01", "endTime": "2020-12-31"}


def test_upstream_error_is_actionable() -> None:
    http = Http([Response({"code": 0, "data": {"token": "token-1"}}), Response({"code": -1, "msg": "not purchased"})])
    client = CsmarClient("account", "password", http=http)

    with pytest.raises(CsmarError, match="not purchased"):
        client.list_databases()
