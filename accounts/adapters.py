from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.internal import flows
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect, reverse
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from phylactery.communication.email import render_html_email, send_single_email_task


class CustomRegularAccountAdapter(DefaultAccountAdapter):
	"""
	Custom adapter for AllAuth accounts. This should disable signing up though the website.
	"""
	def is_open_for_signup(self, request):
		return False
	
	def get_email_verification_redirect_url(self, email_address):
		url = reverse("members:my_profile")
		return url
	
	def send_password_reset_mail(self, user, email, ctx):
		context = {
			"email": email,
			"current_site": get_current_site(self.request),
		}
		context.update(ctx)
		subject = "Reset your Unigames password"
		plaintext_message, html_message = render_html_email(
			template_name="account/email/password_reset.html",
			context=context,
			request=self.request,
		)
		send_single_email_task.delay(
			email_address=email,
			subject=subject,
			message=plaintext_message,
			html_message=html_message,
		)
	
	def send_confirmation_mail(self, request, emailconfirmation, signup):
		context = {
			"user": emailconfirmation.email_address.user,
			"key": emailconfirmation.key,
			"activate_url": self.get_email_confirmation_url(
				request, emailconfirmation
			),
			"email": emailconfirmation.email_address.email,
			"current_site": get_current_site(self.request),
		}
		subject = "Unigames - Please Confirm Your Email Address"
		plaintext_message, html_message = render_html_email(
			template_name="account/email/email_confirmation.html",
			context=context,
			request=self.request,
		)
		send_single_email_task.delay(
			email_address=emailconfirmation.email_address.email,
			subject=subject,
			message=plaintext_message,
			html_message=html_message,
		)
		
	def send_notification_mail(self, template_prefix, user, context=None, email=None):
		# Disabled in our app
		return
	
	def send_account_already_exists_mail(self, email):
		password_reset_url = flows.password_reset.get_reset_password_url(
			self.request,
		)
		context = {
			"password_reset_url": password_reset_url,
			"email": email,
			"current_site": get_current_site(self.request),
		}
		subject = "Unigames Account Already Exists"
		plaintext_message, html_message = render_html_email(
			template_name="account/email/account_already_exists.html",
			context=context,
			request=self.request,
		)
		send_single_email_task.delay(
			email_address=email,
			subject=subject,
			message=plaintext_message,
			html_message=html_message,
		)
		
	def send_mail(self, template_prefix, email, ctx):
		"""
		AllAuth uses the previous four methods to send email.
		We override those so that we can handle the email with
		Celery instead.
		However, one scenario (unknown account) just calls the send_mail
		method directly. We handle that scenario here.
		"""
		if template_prefix == "account/email/unknown_account":
			context = {
				"email": email,
				"current_site": get_current_site(self.request),
			}
			context.update(ctx)
			subject = "Unknown Unigames Account"
			plaintext_message, html_message = render_html_email(
				template_name="account/email/unknown_account.html",
				context=context,
				request=self.request,
			)
			send_single_email_task.delay(
				email_address=email,
				subject=subject,
				message=plaintext_message,
				html_message=html_message,
			)
		else:
			pass


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
	"""
	Custom adapter for AllAuth Social Accounts. This should disable signing up exclusively via Discord.
	"""
	def is_open_for_signup(self, request, sociallogin):
		return False
	
	def pre_social_login(self, request, sociallogin):
		"""
		By default, AllAuth allows for someone to connect as many accounts as they please.
		Since there wasn't an easy way to disable this, this is my workaround.
		Immediately before the connection is processed, check if they have a Discord account linked already.
		If they do, we disallow the connection by redirecting immediately to the profile view with an error message.
		"""
		if request.user.is_authenticated:
			if SocialAccount.objects.filter(
				user=request.user,
				provider="discord"
			).exists():
				# They have an account already
				messages.error(request, "You already have a Discord account linked.")
				raise ImmediateHttpResponse(redirect("members:my_profile"))
	
	def get_connect_redirect_url(self, request, socialaccount):
		"""
		Redirects to the User's profile after connecting an account.
		"""
		url = reverse("members:my_profile")
		return url
