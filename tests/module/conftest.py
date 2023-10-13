import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, cast

import pytest
from pytest_docker.plugin import DockerComposeExecutor  # type: ignore[import]


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    return "acidrain-logging"


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


@dataclass
class DockerLogs:
    executor: DockerComposeExecutor

    def __call__(self, service: str, since: Optional[datetime] = None) -> str:
        cmd = ["logs", "--no-log-prefix"]
        if since:
            cmd += ["--since", since.isoformat()]
        cmd.append(service)

        return cast(bytes, self.executor.execute(" ".join(cmd))).decode().strip()


@pytest.fixture(scope="session")
def docker_logs(docker_compose_executor: DockerComposeExecutor) -> Callable[[str], str]:
    return DockerLogs(docker_compose_executor)


@pytest.fixture(scope="session")
def docker_cleanup() -> Optional[str]:
    return None
