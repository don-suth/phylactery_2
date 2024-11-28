import re

import css_inline
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.sites.models import Site
from django.core.mail import get_connection, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

multiple_newline = re.compile(r"\n{2,}")
logger = get_task_logger(__name__)
inliner = css_inline.CSSInliner(
	load_remote_stylesheets=False
)


def render_html_email(template_name, context, request=None):
	"""
		Renders an email template in both html and plaintext.
		Normally, this would construct an Email object and return it.
		However, that isn't passable with Celery.
		So we only render the email bodies and return those.
	"""
	context["protocol"] = "https://"
	context["domain"] = Site.objects.get_current().domain
	
	html_message = render_to_string(template_name, context, request=request)
	# For best HTML email results, CSS has to be put on elements inline.
	html_message = inliner.inline(html_message)
	
	# Process the plaintext version
	context["override_base"] = "email/email_base.txt"
	plaintext_message = render_to_string(template_name, context, request=request)
	# Remove excess whitespace
	plaintext_message = "\n".join(line.strip() for line in plaintext_message.splitlines())
	# Remove leftover HTML tags from the plaintext message
	plaintext_message = strip_tags(plaintext_message)
	plaintext_message = re.sub(multiple_newline, "\n\n", plaintext_message)
	return plaintext_message, html_message


@shared_task(name="send_single_mail_task", rate_limit="1/s")
def send_single_email_task(email_address, subject, message, html_message=None, connection=None, log=True):
	"""
		Sends a single email to a single email address asynchronously.
	"""
	if connection is None:
		connection = get_connection()
		connection.open()

	send_mail(
		subject=subject,
		message=message,
		from_email=None,
		recipient_list=[email_address],
		html_message=html_message,
		connection=connection
	)
	if log:
		logger.info(f"Sent email to {email_address}.")


@shared_task(name="send_mass_email_task")
def send_mass_email_task(email_address_list, subject, message, html_message=None):
	"""
		Sends a single email to many email addresses.
		Intended for mailing list purposes.
		It calls the send_single_email_task a bunch of times,
		so that everything goes through its rate limit.
	"""
	connection = get_connection()
	connection.open()
	for email_address in email_address_list:
		send_single_email_task.delay(
			email_address=email_address,
			subject=subject,
			message=message,
			html_message=html_message,
			connection=connection,
			log=False
		)
	connection.close()
	logger.info(f"Sent emails to {len(email_address_list)} recipients.")
