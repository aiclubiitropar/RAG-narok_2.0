from celery import Celery
import os

redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url,
    include=["worker.tasks.email_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Example config for periodic tasks (email fetching)
celery_app.conf.beat_schedule = {
    "fetch-emails-every-5-minutes": {
        "task": "worker.tasks.email_tasks.fetch_and_summarize_emails",
        "schedule": 300.0, # 5 minutes
    },
    "remove-duplicates-every-5-minutes": {
        "task": "worker.tasks.email_tasks.maintenance_cleanup_task",
        "schedule": 300.0, # 5 minutes
    },
}
