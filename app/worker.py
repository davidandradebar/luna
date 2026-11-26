"""Punto de entrada del worker RQ."""

from redis import Redis
from rq import Queue, Worker

from app.config import Config


def main() -> None:
    connection = Redis.from_url(Config.REDIS_URL)
    Worker([Queue(Config.RQ_QUEUE, connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
