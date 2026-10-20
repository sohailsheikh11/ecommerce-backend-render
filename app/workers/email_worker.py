
from rq import SimpleWorker

from app.core.notification_queue import email_queue


def main():
    worker = SimpleWorker(
        queues=[email_queue],
        connection=email_queue.connection,
    )

    print("Email notification worker is starting...")
    print(f"Listening on queue: {email_queue.name}")

    worker.work()


if __name__ == "__main__":
    main()
