from __future__ import annotations

import os

import pytest
from pytest_docker.plugin import DockerComposeExecutor  # type: ignore[import]


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    return "acidrain-workbench"


@pytest.fixture(scope="session")
def docker_ip(docker_ip: str) -> str:
    return os.getenv("DOCKER_NETWORK_IP", docker_ip)


@pytest.fixture(scope="session")
def docker_compose_executor(
    docker_compose_command: str,
    docker_compose_file: str,
    docker_compose_project_name: str,
) -> DockerComposeExecutor:
    return DockerComposeExecutor(
        docker_compose_command, docker_compose_file, docker_compose_project_name
    )


@pytest.fixture(scope="session")
def docker_cleanup() -> str | None:
    return None
