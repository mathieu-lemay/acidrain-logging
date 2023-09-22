import json
import socket
from builtins import reversed
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import ANY
from urllib.parse import urlparse

import httpx
import pytest
from httpx import AsyncClient, RequestError
from pytest_docker.plugin import DockerComposeExecutor, Services  # type: ignore[import]


@pytest.fixture(scope="session")
def api_base_url(docker_ip: str, docker_services: Services) -> str:
    port = docker_services.port_for("api", 8000)

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


@pytest.fixture()
async def api_client(api_base_url: str) -> AsyncGenerator[AsyncClient, None]:
    async with httpx.AsyncClient(base_url=api_base_url) as client:
        yield client


@pytest.mark.usefixtures("api_client")  # ensure the api is up and running
async def test_api_logging_uses_structlog(
    docker_compose_executor: DockerComposeExecutor,
) -> None:
    api_logs = (
        docker_compose_executor.execute("logs --no-log-prefix api").decode().strip()
    ).split("\n")

    for entry in map(json.loads, filter(None, reversed(api_logs))):
        if entry["message"] == "Application startup complete.":
            break
    else:  # pragma: no cover
        pytest.fail("Could not find app startup log")

    # There was a json log, we just need to ensure the presence of some values.
    assert entry["dd.env"] == "testing"
    assert entry["dd.service"] == "test-api"
    assert entry["dd.version"] == "0.0.0-dev"
    assert datetime.strptime(  # noqa: DTZ007: Timezone is irrelevant
        entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
    )


async def test_request_logging_includes_all_metadata(
    api_client: AsyncClient,
    api_base_url: str,
    docker_compose_executor: DockerComposeExecutor,
) -> None:
    timestamp = datetime.now(tz=timezone.utc)

    resp = await api_client.get("/")
    assert resp.is_success

    api_logs = (
        docker_compose_executor.execute(
            f"logs --no-log-prefix --since {timestamp.isoformat()} api"
        )
        .decode()
        .strip()
    )

    parsed_url = urlparse(api_base_url)

    entry = json.loads(api_logs)
    assert entry["request"] == {
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
    socket.inet_aton(entry["request"]["client"]["remote_ip"])

    # Ensure elapsed is a valid float
    assert isinstance(entry["request"]["response"]["elapsed"], float)