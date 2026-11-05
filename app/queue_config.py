import os
from redis import Redis
from rq import Queue, Retry

redis_connection = Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

high_queue = Queue("high", connection=redis_connection)
medium_queue = Queue("medium", connection=redis_connection)
low_queue = Queue("low", connection=redis_connection)

job_retry = Retry(max=3, interval=5)

