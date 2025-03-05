from celery import shared_task
from phylactery.communication.email import render_html_email, send_single_email_task
from django.utils import timezone
from library.models import Reservation


@shared_task(name="check_for_unused_reservations")
def check_for_unused_reservations():
	"""
	Check for reservations that are active, but their borrow date has passed.
	Sets them to in-active, so that the Items in that reservation can be borrowed normally.
	Intended to be run every day.
	"""
	active_reservations = Reservation.objects.filter(
		is_active=True,
		requested_date_to_borrow__lt=timezone.localdate()
	)
	active_reservations.update(is_active=False)
	

def send_borrow_receipt(email_address, borrower_name, items, authorised_by):
	context = {
		"borrower_name": borrower_name,
		"items": items,
		"gatekeeper": authorised_by,
		"today": timezone.now(),
	}
	subject = "Unigames Library Borrowing Receipt"
	plaintext_message, html_message = render_html_email(
		template_name="library/email/borrow_receipt.html",
		context=context,
	)
	send_single_email_task.delay_on_commit(
		email_address=email_address,
		subject=subject,
		message=plaintext_message,
		html_message=html_message
	)


def send_return_receipt(email_address, borrower_name, items, authorised_by):
	context = {
		"borrower_name": borrower_name,
		"items": items,
		"gatekeeper": authorised_by,
		"today": timezone.now(),
	}
	subject = "Unigames Library Return Receipt"
	plaintext_message, html_message = render_html_email(
		template_name="library/email/return_receipt.html",
		context=context,
	)
	send_single_email_task.delay_on_commit(
		email_address=email_address,
		subject=subject,
		message=plaintext_message,
		html_message=html_message
	)
