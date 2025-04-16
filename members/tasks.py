from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta
from phylactery.communication.discord import send_to_operations

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


@shared_task(name="new_finance_record_digest")
def new_finance_record_digest():
	"""
		Scheduled task. (One a day.)
		Send a discord notification to the Treasurer if any unresolved finance records
		were created in the last 24 hours.
		
		If there were none in the last 24 hours, but there are still some unresolved ones,
		we send a reminder to the Treasurer every Wednesday.
	"""
	from members.models import FinanceRecord
	new_records_count = FinanceRecord.objects.filter(added_at__gte=timezone.now()-timedelta(hours=24), resolved=False).count()
	outstanding_records_count = FinanceRecord.objects.filter(resolved=False).count() - new_records_count
	discord_message = f"Greetings <@&612900808580923393>! I hope you are having a nice day!"
	send_message = False
	if new_records_count > 0:
		send_message = True
		discord_message += f"\nJust letting you know: {new_records_count} new finance record(s) have been added in the last 24 hours."
		if outstanding_records_count > 0:
			discord_message += f"\nIn addition, there are still {outstanding_records_count} previous finance record(s) outstanding that haven't been resolved yet."
	elif outstanding_records_count > 0 and timezone.localdate().weekday() == 3:
		send_message = True
		discord_message += f"\nAs a small reminder, there are still {outstanding_records_count} previous finance record(s) outstanding that haven't been resolved yet."
	
	if send_message:
		send_to_operations(discord_message)
