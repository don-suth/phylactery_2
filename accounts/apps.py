from django.apps import AppConfig
from allauth.socialaccount.signals import (
	social_account_added,
	social_account_updated,
	social_account_removed,
)
from .signals import update_discord_link_details, delete_discord_link


class AccountsConfig(AppConfig):
	default_auto_field = 'django.db.models.AutoField'
	name = 'accounts'
	
	def ready(self):
		social_account_added.connect(update_discord_link_details, dispatch_uid="update_on_add")
		social_account_updated.connect(update_discord_link_details, dispatch_uid="update_on_update")
		social_account_removed.connect(delete_discord_link, dispatch_uid="update_on_remove")
