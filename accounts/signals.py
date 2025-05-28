from redis import Redis
from django.conf import settings


def update_discord_link_details(sender, request, sociallogin, **kwargs):
	"""
	Callback received when a SocialAccount (Discord only at this stage) is added or updated.
	If they:
		- Have linked a Discord account
		- Are a current member
		- Are not excluded
	Then we add them to a redis dictionary, mapping their Discord UID to their short name.
	"""
	social_account = sociallogin.account
	member = social_account.user.member
	with Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True) as r:
		if member.is_valid_member():
			r.hset("lich:linked_accounts", social_account.uid, social_account.user.member.short_name)
		else:
			r.hdel("lich:linked_accounts", social_account.uid)
	
	
def delete_discord_link(sender, request, socialaccount, **kwargs):
	"""
	Callback received when a SocialAccount (Discord only at this stage) is removed or unlinked.
	Remove them from the redis dictionary mapping.
	"""
	social_account = socialaccount
	with Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True) as r:
		r.hdel("lich:linked_accounts", social_account.uid)
