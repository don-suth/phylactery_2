from celery import shared_task
from phylactery.tasks import render_html_email, send_single_email_task


def send_borrow_receipt(email_address, borrower_name, items, authorised_by):
	context = {
		"borrower_name": borrower_name,
		"items": items,
		"gatekeeper": authorised_by,
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