from dataclasses import dataclass
from functools import partial
from time import perf_counter, sleep
from typing import Any, Callable, Dict, Generic, Tuple, TypeVar

# TODO: Extract this to a reusable lib, test it and remove no cover directives

T = TypeVar("T")


@dataclass
class Probe(Generic[T]):
    target: Callable[..., T]

    def until(
        self, matcher: Callable[[T], bool], *, timeout_s: int = 30, interval_s: int = 1
    ) -> T:
        start_tm = perf_counter()

        while perf_counter() - start_tm < timeout_s:
            res = self.target()

            if matcher(res):
                return res

            sleep(interval_s)  # pragma: no cover

        raise TimeoutError  # pragma: no cover


def retry(
    target: Callable[..., T], *args: Tuple[Any], **kwargs: Dict[str, Any]
) -> Probe[T]:
    return Probe(target=partial(target, *args, **kwargs))
