import json
import socket
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import ANY
from urllib.parse import urlparse

import httpx
import pytest
from httpx import AsyncClient, RequestError
from pytest_docker.plugin import Services

from tests.module.conftest import DockerLogs


@pytest.fixture(scope="session")
def api_base_url(docker_ip: str, docker_services: Services) -> str:
    port = docker_services.port_for("flask", 8000)

    base_url = f"http://{docker_ip}:{port}"

    def _healthcheck() -> bool:
        try:
            resp = httpx.get(base_url)
        except RequestError:  # pragma: no cover
            return False
        else:
            return resp.is_success

    docker_services.wait_until_responsive(_healthcheck, timeout=5, pause=0.05)

    return base_url


@pytest.fixture
async def api_client(api_base_url: str) -> AsyncGenerator[AsyncClient, None]:
    async with httpx.AsyncClient(base_url=api_base_url) as client:
        yield client


async def test_request_logging_includes_all_metadata(
    api_client: AsyncClient, api_base_url: str, docker_logs: DockerLogs
) -> None:
    timestamp = datetime.now(tz=UTC)

    resp = await api_client.get("/")
    assert resp.is_success

    api_logs = docker_logs("flask", since=timestamp)

    parsed_url = urlparse(api_base_url)

    entry = json.loads(api_logs)
    assert entry["http"] == {
        "client": {
            "remote_ip": ANY,
            "user_agent": f"python-httpx/{httpx.__version__}",
        },
        "method": "GET",
        "request": {
            "path_params": {},
            "query_params": {},
        },
        "response": {"elapsed": ANY, "status_code": 200},
        "url": {
            "host": parsed_url.hostname,
            "path": "/",
            "scheme": parsed_url.scheme,
        },
    }

    # Ensure remote IP is a valid IP address
    socket.inet_aton(entry["http"]["client"]["remote_ip"])

    # Ensure elapsed is a valid float
    assert isinstance(entry["http"]["response"]["elapsed"], float)
