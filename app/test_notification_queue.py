
from app.core.notification_queue import email_queue

print("Queue name:", email_queue.name)
print("Redis connection:", email_queue.connection.ping())
print("Waiting jobs:", email_queue.count)
