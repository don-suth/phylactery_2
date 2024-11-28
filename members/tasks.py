from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(name="cleanup_permissions")
def cleanup_permissions():
	"""
		Scheduled task. (Once a day.)
		Syncs the permissions of every user,
		so that permissions are removed when ranks expire.
	"""
	from members.models import Member
	successful = 0
	for member in Member.objects.all():
		if member.sync_permissions():
			successful += 1
	logger.info(f"Synced permissions of {successful} members.")
