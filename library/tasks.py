import datetime
from celery import shared_task
from celery.utils.log import get_task_logger
from phylactery.communication.email import render_html_email, send_single_email_task
from django.utils import timezone
from library.models import Reservation, BorrowRecord
from collections import defaultdict

logger = get_task_logger(__name__)


@shared_task(name="send_due_date_reminder_task")
def send_due_date_reminder_task():
	"""
	Scheduled task, once a day.
	Sends a reminder email to all internal borrowers of Items that
	are due either today, or tomorrow.
	
	External borrowers are not currently supported,
	as we don't store an email for them.
	"""
	today = timezone.localdate()
	tomorrow = today + datetime.timedelta(days=1)
	records_due_today = BorrowRecord.objects.filter(returned=False, due_date=today).prefetch_related("borrower")
	records_due_tomorrow = BorrowRecord.objects.filter(returned=False, due_date=tomorrow).prefetch_related("borrower")
	
	logger.info(f"Library: {records_due_today.count()} record(s) due today.")
	borrowers_with_records_due_today = defaultdict(list)
	for record in records_due_today:
		# Currently, we can't email external borrowers.
		if record.borrower.is_external is False:
			borrowers_with_records_due_today[record.borrower.internal_member].append(record)
	
	for internal_member, record_list in borrowers_with_records_due_today.values():
		context = {
			"member": internal_member,
			"due_date": today,
			"record_list": record_list
		}
		plaintext_message, html_message = render_html_email(
			template_name="library/email/reminder_today.html",
			context=context,
		)
		send_single_email_task.delay(
			email_address=internal_member.email,
			subject="Reminder - Unigames Items Due Today",
			message=plaintext_message,
			html_message=html_message,
		)
	
	logger.info(f"Library: {records_due_tomorrow.count()} records due tomorrow.")
	borrowers_with_records_due_tomorrow = defaultdict(list)
	for record in records_due_tomorrow:
		# Currently, we can't email external borrowers.
		if record.borrower.is_external is False:
			borrowers_with_records_due_tomorrow[record.borrower.internal_member].append(record)
	
	for internal_member, record_list in borrowers_with_records_due_tomorrow.values():
		context = {
			"member": internal_member,
			"due_date": tomorrow,
			"record_list": record_list
		}
		plaintext_message, html_message = render_html_email(
			template_name="library/email/reminder_tomorrow.html",
			context=context,
		)
		send_single_email_task.delay(
			email_address=internal_member.email,
			subject="Reminder - Unigames Items Due Tomorrow",
			message=plaintext_message,
			html_message=html_message,
		)


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
