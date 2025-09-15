from celery import shared_task
from celery.utils.log import get_task_logger
from allauth.socialaccount.models import SocialAccount
from redis import Redis
from django.conf import settings

logger = get_task_logger(__name__)


@shared_task(name="check_discord_account_links_task")
def check_discord_account_links_task():
	"""
	Iterates through every Discord account linked to Unigames,
	checks if they are a valid member.
	If they are, update their entry in the Redis dict.
	If they aren't, remove them from the Redis dict.
	
	Intended to be run each day.
	"""
	accounts = SocialAccount.objects.prefetch_related("user__member").all()
	updated = 0
	removed = 0
	with Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True) as r:
		for social_account in accounts:
			member = social_account.user.member
			if member.is_valid_member():
				r.hset("lich:linked_accounts", social_account.uid, member.short_name)
				updated += 1
			else:
				r.hdel("lich:linked_accounts", social_account.uid)
				removed += 1
	logger.info(f"Updated Discord permissions for {updated} members. Removed permissions for {removed} members.")
	
	
