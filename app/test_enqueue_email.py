
from app.core.notification_queue import email_queue
from app.tasks.email_tasks import send_email_notification


recipient = input("Enter an email address you can access: ")

job = email_queue.enqueue(
    send_email_notification,
    recipient,
    "Test Email - E-commerce Notifications",
    (
        "Hello!\n\n"
        "This is a test email from your FastAPI "
        "e-commerce notification queue.\n\n"
        "If you received this email, your Redis queue, "
        "RQ worker, and Brevo SMTP integration are working."
    ),
)

print("Email job added to the queue.")
print("Job ID:", job.id)
print("Initial job status:", job.get_status())
