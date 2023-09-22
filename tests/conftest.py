from time import time

import pytest


@pytest.fixture(scope="session", autouse=True)
def faker_seed() -> float:
    return time()
