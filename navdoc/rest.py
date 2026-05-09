import json
from collections.abc import AsyncGenerator

import httpx

from .exceptions import AuthError, NavdocError

REST_BASE_URL = "https://api.navdoc.dev"


class NavdocREST:
    def __init__(self, api_key: str) -> None:
        self._headers = {"authorization": f"Bearer {api_key}"}

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{REST_BASE_URL}{path}",
                headers=self._headers,
                params={k: v for k, v in (params or {}).items() if v is not None},
            )
        self._raise_for_status(resp)
        return resp.json()

    async def post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{REST_BASE_URL}{path}",
                headers=self._headers,
                json={k: v for k, v in body.items() if v is not None},
            )
        self._raise_for_status(resp)
        return resp.json()

    async def patch(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{REST_BASE_URL}{path}",
                headers=self._headers,
                json={k: v for k, v in body.items() if v is not None},
            )
        self._raise_for_status(resp)
        return resp.json()

    async def delete(self, path: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{REST_BASE_URL}{path}",
                headers=self._headers,
            )
        self._raise_for_status(resp)

    async def stream_post(self, path: str, body: dict) -> AsyncGenerator[dict, None]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
            async with client.stream(
                "POST",
                f"{REST_BASE_URL}{path}",
                headers={**self._headers, "accept": "text/event-stream"},
                json={k: v for k, v in body.items() if v is not None},
            ) as resp:
                if resp.status_code in (401, 403):
                    raise AuthError(f"Authentication failed ({resp.status_code})")
                if resp.status_code >= 400:
                    raise NavdocError(f"API error {resp.status_code}")
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code in (401, 403):
            raise AuthError(f"Authentication failed ({resp.status_code}): {resp.text}")
        if resp.status_code >= 400:
            raise NavdocError(f"API error {resp.status_code}: {resp.text}")
