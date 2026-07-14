from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx


class RuntimeBridgeError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503, error_code: str = "bridge_unavailable"):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class AgentRuntimeBridgeClient:
    def __init__(
        self,
        socket_path: str | Path | None = None,
        token_file: str | Path | None = None,
        *,
        timeout: float | None = None,
    ):
        self.socket_path = str(socket_path or os.getenv("QINGLUO_AGENT_BRIDGE_SOCKET", "/run/agent-bridge/runtime-bridge.sock"))
        self.token_file = Path(token_file or os.getenv("QINGLUO_AGENT_BRIDGE_TOKEN_FILE", "/run/agent-bridge/token"))
        self.timeout = timeout or float(os.getenv("QINGLUO_AGENT_BRIDGE_TIMEOUT_SECONDS", "30"))

    def _headers(self) -> dict[str, str]:
        try:
            token = self.token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeBridgeError("Agent runtime bridge credentials are unavailable") from exc
        if not token:
            raise RuntimeBridgeError("Agent runtime bridge credentials are empty")
        return {"Authorization": f"Bearer {token}"}

    def _client(self, *, timeout: float | None = None) -> httpx.AsyncClient:
        transport = httpx.AsyncHTTPTransport(uds=self.socket_path)
        return httpx.AsyncClient(
            transport=transport,
            base_url="http://agent-runtime-bridge",
            timeout=timeout or self.timeout,
            headers=self._headers(),
        )

    async def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._client() as client:
                response = await client.request(method, path, json=json, params=params)
        except (httpx.HTTPError, OSError) as exc:
            raise RuntimeBridgeError("Agent runtime bridge is unavailable") from exc
        if response.is_error:
            try:
                detail = response.json().get("detail", {})
            except ValueError:
                detail = {}
            if isinstance(detail, str):
                message, error_code = detail, "runtime_error"
            else:
                message = str(detail.get("message") or "Agent runtime request failed")
                error_code = str(detail.get("code") or "runtime_error")
            raise RuntimeBridgeError(message, status_code=response.status_code, error_code=error_code)
        return response.json()

    async def status(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/status")

    async def history(self, *, runtime: str, external_session_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        return await self._request("POST", "/v1/history", json={
            "runtime": runtime,
            "external_session_id": external_session_id,
            "cursor": cursor,
            "limit": limit,
        })

    async def search_history(self, *, runtime: str, external_session_id: str, query: str, limit: int) -> dict[str, Any]:
        return await self._request("POST", "/v1/history/search", json={
            "runtime": runtime,
            "external_session_id": external_session_id,
            "query": query,
            "limit": limit,
        })

    async def start_turn(
        self,
        *,
        runtime: str,
        external_session_id: str,
        text: str,
        model: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await self._request("POST", "/v1/turns", json={
            "runtime": runtime,
            "external_session_id": external_session_id,
            "text": text,
            "model": model,
            "attachments": attachments or [],
        })

    async def models(self, *, runtime: str, external_session_id: str) -> dict[str, Any]:
        return await self._request("POST", "/v1/models", json={
            "runtime": runtime,
            "external_session_id": external_session_id,
        })

    async def rename(self, *, runtime: str, external_session_id: str, name: str) -> dict[str, Any]:
        return await self._request("POST", "/v1/rename", json={
            "runtime": runtime,
            "external_session_id": external_session_id,
            "name": name,
        })

    async def interrupt(self, run_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/v1/turns/{run_id}/interrupt")

    async def approve(self, run_id: str, approval_id: str, decision: str) -> dict[str, Any]:
        return await self._request("POST", f"/v1/turns/{run_id}/approvals/{approval_id}", json={"decision": decision})

    async def delete_source(self, *, runtime: str, external_session_id: str) -> dict[str, Any]:
        return await self._request("POST", "/v1/delete", json={
            "runtime": runtime,
            "external_session_id": external_session_id,
        })

    async def stream_events(self, run_id: str) -> AsyncIterator[bytes]:
        try:
            async with self._client(timeout=300) as client:
                async with client.stream("GET", f"/v1/turns/{run_id}/events") as response:
                    if response.is_error:
                        raise RuntimeBridgeError("Unable to stream runtime events", status_code=response.status_code)
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except RuntimeBridgeError:
            raise
        except (httpx.HTTPError, OSError) as exc:
            raise RuntimeBridgeError("Agent runtime event stream disconnected") from exc
