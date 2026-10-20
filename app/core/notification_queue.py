
from rq import Queue

from app.core.redis_client import redis_client


email_queue = Queue(
    name="email_notifications",
    connection=redis_client,
)

