import structlog
from celery import Celery
from structlog.stdlib import BoundLogger

from acidrain_logging.celery.signals import connect_signals

app = Celery(broker="amqp://broker:5672//", backend="file:///var/run/celery")

connect_signals()


log: BoundLogger = structlog.get_logger()


@app.task()
def dummy_task(n: int) -> int:
    log.info("Running dummy task with n=%d", n)
    return n
