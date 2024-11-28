import os
from django.conf import settings
from celery import Celery

# https://docs.celeryq.dev/en/main/django/first-steps-with-django.html#django-first-steps

# Set the default Django settings module for Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phylactery.settings")
app = Celery("phylactery")

# Configure Celery
app.config_from_object(
	f"django.conf:settings", namespace="CELERY"
)

# Load all tasks from registered django apps
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
	print(f"Request: {self.request!r}")
