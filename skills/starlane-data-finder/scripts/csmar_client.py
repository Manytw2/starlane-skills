"""Small authenticated client for CSMAR's Python data-service endpoints."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import urllib3


class CsmarError(RuntimeError):
    """An actionable error returned by CSMAR or its transport."""


class HttpClient(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class CsmarQuery:
    table_code: str
    columns: list[str]
    condition: str
    start_date: str | None
    end_date: str | None

    def payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "table": self.table_code,
            "columns": self.columns,
            "condition": self.condition or "1=1",
        }
        if self.start_date:
            data["startTime"] = self.start_date
        if self.end_date:
            data["endTime"] = self.end_date
        return data


class CsmarClient:
    BASE_URL = "https://data.csmar.com/api"

    def __init__(self, account: str, password: str, http: HttpClient | None = None) -> None:
        self._account = account
        self._password = password
        self._http = http or urllib3.PoolManager()
        self._token: str | None = None

    def list_databases(self) -> Any:
        return self._get("/csmar-main/python/listDbs", include_belong=True)

    def list_tables(self, database_name: str) -> Any:
        return self._get("/csmar-main/python/listTables", fields={"dbName": database_name}, include_belong=True)

    def describe_table(self, table_code: str) -> Any:
        return self._get("/csmar-main/python/listFields", fields={"table": table_code}, include_belong=True)

    def query_count(self, query: CsmarQuery) -> int:
        data = self._post("/csmar-single/pythonQuery/getDataCount", query.payload())
        try:
            return int(data)
        except (TypeError, ValueError) as error:
            raise CsmarError("CSMAR returned an invalid row count.") from error

    def query_sample(self, query: CsmarQuery, sample_rows: int) -> Any:
        sample = CsmarQuery(query.table_code, query.columns, f"({query.condition or '1=1'}) limit 0,{sample_rows}", query.start_date, query.end_date)
        return self._post("/csmar-single/pythonQuery/query", sample.payload())

    def start_download(self, query: CsmarQuery) -> str:
        data = self._post("/csmar-main/python/pack", query.payload())
        sign_code = str(data or "").strip()
        if not sign_code:
            raise CsmarError("CSMAR did not return a download package identifier.")
        return sign_code

    def package_status(self, sign_code: str) -> dict[str, Any]:
        data = self._get(f"/csmar-main/python/getPackResult/{sign_code}", include_belong=True)
        if not isinstance(data, dict):
            raise CsmarError("CSMAR returned an invalid download package status.")
        return data

    def download(self, url: str) -> bytes:
        response = self._http.request("GET", url)
        if response.status >= 400:
            raise CsmarError(f"CSMAR archive download failed with HTTP {response.status}.")
        return bytes(response.data)

    def _login(self) -> None:
        response = self._http.request(
            "POST", f"{self.BASE_URL}/csmar-main/login",
            fields={"account": self._account, "pwd": self._password, "force": "1", "clientType": "5", "version": "1.0.2"},
        )
        result = self._decode_response(response)
        token = str(result.get("data", {}).get("token", "")).strip()
        if result.get("code") != 0 or not token:
            raise CsmarError(str(result.get("msg") or "CSMAR authentication failed."))
        self._token = token

    def _headers(self, include_belong: bool, json_body: bool = False) -> dict[str, str]:
        if not self._token:
            self._login()
        headers = {"Lang": "0", "Token": self._token or ""}
        if include_belong:
            headers["belong"] = "0"
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _get(self, path: str, fields: dict[str, str] | None = None, include_belong: bool = False) -> Any:
        response = self._http.request("GET", f"{self.BASE_URL}{path}", fields=fields, headers=self._headers(include_belong))
        return self._require_success(self._decode_response(response))

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        response = self._http.request("POST", f"{self.BASE_URL}{path}", body=json.dumps(payload).encode(), headers=self._headers(False, json_body=True))
        return self._require_success(self._decode_response(response))

    @staticmethod
    def _decode_response(response: Any) -> dict[str, Any]:
        if response.status >= 400:
            raise CsmarError(f"CSMAR returned HTTP {response.status}.")
        try:
            payload = json.loads(response.data.decode("utf-8"))
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CsmarError("CSMAR returned an invalid JSON response.") from error
        if not isinstance(payload, dict):
            raise CsmarError("CSMAR returned an invalid response shape.")
        return payload

    @staticmethod
    def _require_success(payload: dict[str, Any]) -> Any:
        if payload.get("code") != 0:
            raise CsmarError(str(payload.get("msg") or "CSMAR request failed."))
        return payload.get("data")
