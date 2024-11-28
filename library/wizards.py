import datetime

from django.contrib import messages
from django.core.exceptions import SuspiciousOperation
from django.forms import formset_factory
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.utils.decorators import method_decorator
from formtools.wizard.views import SessionWizardView
from members.decorators import gatekeeper_required

from library.forms import SelectLibraryItemsForm, ItemDueDateForm, InternalBorrowerDetailsForm, ExternalBorrowerDetailsForm, ReservationSelectItemForm
from library.models import BorrowerDetails, BorrowRecord, Reservation
from library.tasks import send_borrow_receipt


ItemDueDateFormset = formset_factory(ItemDueDateForm, extra=0)
ReservationSelectItemsFormset = formset_factory(ReservationSelectItemForm, extra=0)


def is_external_reservation(wizard):
	reservation = wizard.get_reservation()
	return reservation.is_external


def is_internal_reservation(wizard):
	return not is_external_reservation(wizard)


@method_decorator(gatekeeper_required, name="dispatch")
class InternalBorrowItemsWizard(SessionWizardView):
	"""
	This view handles the borrowing of Library Items in a "wizard", which is
	multiple forms working together in one view.
	"""
	form_list = [
		("select", SelectLibraryItemsForm),
		("due_dates", ItemDueDateFormset),
		("details", InternalBorrowerDetailsForm),
	]
	template_name = "library/library_borrow_wizard.html"
	
	def render_goto_step(self, *args, **kwargs):
		"""
		This method overrides the WizardView Method.
		When going back a step, it allows the form to validate data that you may have already entered.
		If so, then it saves that data, so that when you return to that step, your data will be safe.
		"""
		form = self.get_form(data=self.request.POST, files=self.request.FILES)
		if form.is_valid():
			self.storage.set_step_data(self.steps.current, self.process_step(form))
			self.storage.set_step_files(self.steps.current, self.process_step_files(form))
		return super().render_goto_step(*args, **kwargs)
	
	def get_form_initial(self, step):
		"""
		This method overrides the WizardView method.
		Adds in the initial data to the formset in the second stop, allowing the gatekeeper to modify item due dates.
		"""
		if step == "due_dates":
			cleaned_data = self.get_cleaned_data_for_step("select")
			cleaned_items = cleaned_data["items"]
			initial_form_data = []
			for item in cleaned_items:
				initial_form_data.append({
					"item": item,
					"due_date": item.get_availability_info()["max_due_date"]
				})
			return initial_form_data
		return super().get_form_initial(step)
	
	def process_step(self, form):
		"""
		This method overrides the WizardView method.
		Used to trigger a warning if some (but not all) of the items selected in step 1 are not available.
		"""
		if self.steps.current == "select":
			# Check if there are any rejected items.
			if form.rejected_items:
				messages.error(
					self.request,
					f"The following items are not available at the moment: {', '.join(form.rejected_items)}. "
					"If you think this is incorrect, please contact the Librarian."
				)
			if form.different_due:
				messages.warning(
					self.request,
					"One or more of the below items has a shorter due-date than the default (2 weeks). "
					"They have been highlighted in Yellow. Please verify that this still suits the borrower."
				)
		return super().process_step(form)
	
	def done(self, form_list, **kwargs):
		"""
		When the form is submitted entirely, we first validate that no manipulation has occurred.
		Then we create the BorrowingRecords and all related objects.
		This includes:
			- Creating a new BorrowerDetails object
			- Create a new BorrowRecord object for each Item being borrowed.
			- Email the borrower a receipt.
		"""
		cleaned_data = self.get_all_cleaned_data()
		
		# Validate the items from the form.
		# We put the item data in Step 2 to easily track it,
		# but we must make sure it hasn't been manipulated.
		
		try:
			for item, item_due_date_form in zip(cleaned_data["items"], cleaned_data["formset-due_dates"], strict=True):
				if item != item_due_date_form["item"]:
					raise SuspiciousOperation("Item data has been tampered with or is missing.")
		except ValueError:
			raise SuspiciousOperation("Item data has been tampered with or is missing.")
		
		new_borrower_details = BorrowerDetails.objects.create(
			is_external=False,
			internal_member=cleaned_data["member"],
			borrower_name=cleaned_data["member"].long_name,
			borrower_address=cleaned_data["address"],
			borrower_phone=cleaned_data["phone_number"],
			borrow_authorised_by=self.request.user.member.long_name,
		)
		
		borrowed_items = []
		for item_due_date_form in cleaned_data["formset-due_dates"]:
			BorrowRecord.objects.create(
				item=item_due_date_form["item"],
				borrower=new_borrower_details,
				due_date=item_due_date_form["due_date"],
			)
			borrowed_items.append((item_due_date_form["item"], item_due_date_form["due_date"]))
		
		messages.success(self.request, "The items were successfully borrowed!")
		send_borrow_receipt(
			email_address=cleaned_data["member"].email,
			borrower_name=cleaned_data["member"].long_name,
			items=borrowed_items,
			authorised_by=self.request.user.member.long_name,
		)
		
		return redirect("library:dashboard")


@method_decorator(gatekeeper_required, name="dispatch")
class InternalReservationBorrowItemsWizard(SessionWizardView):
	"""
	This view handles the borrowing of Library Items in a "wizard", which is
	multiple forms working together in one view.
	This Wizard handles borrowing an Internal Reservation.
	"""
	form_list = [
		("select", ReservationSelectItemsFormset),
		("internal_details", InternalBorrowerDetailsForm),
	]
	template_name = "library/library_reservation_borrow_wizard.html"
	
	def get_reservation(self):
		reservation = get_object_or_404(Reservation, pk=self.kwargs["pk"])
		if not reservation.is_active:
			raise Http404("The requested reservation is not active.")
		if reservation.requested_date_to_borrow != datetime.date.today():
			raise Http404("The requested reservation is not for borrowing today.")
		if reservation.is_external:
			raise Http404("The requested reservation is an external reservation.")
		return reservation
	
	def render_goto_step(self, *args, **kwargs):
		"""
		This method overrides the WizardView Method.
		When going back a step, it allows the form to validate data that you may have already entered.
		If so, then it saves that data, so that when you return to that step, your data will be safe.
		"""
		form = self.get_form(data=self.request.POST, files=self.request.FILES)
		if form.is_valid():
			self.storage.set_step_data(self.steps.current, self.process_step(form))
			self.storage.set_step_files(self.steps.current, self.process_step_files(form))
		return super().render_goto_step(*args, **kwargs)
	
	def get_form_initial(self, step):
		"""
		This method overrides the WizardView method.
		Initialises the due date information for the chosen reservation.
		"""
		if step == "select":
			initial_form_data = []
			reservation = self.get_reservation()
			for item in reservation.reserved_items.all():
				availability_info = item.get_availability_info()
				if availability_info["in_clubroom"]:
					initial_form_data.append({
						"item": item,
						"due_date": reservation.requested_date_to_return,
						"selected": False,
					})
			return initial_form_data
		return super().get_form_initial(step)
	
	def done(self, form_list, **kwargs):
		"""
		When the form is submitted entirely, we first validate that no manipulation has occurred.
		Then we create the BorrowingRecords and all related objects.
		This includes:
			- Creating a new BorrowerDetails object
			- Create a new BorrowRecord object for each Item being borrowed.
			- Email the borrower a receipt.
		"""
		reservation = self.get_reservation()
		cleaned_data = self.get_all_cleaned_data()
		
		# Verify that each item from Step 1 is actually part of the reservation,
		# and determine which items are being borrowed now.
		
		selected_items = []
		for selected_item_form in cleaned_data["formset-select"]:
			if selected_item_form["item"] not in reservation.reserved_items.all():
				raise SuspiciousOperation("Item data has been tampered with or is missing.")
			else:
				if selected_item_form["selected"] is True:
					selected_items.append(selected_item_form["item"])
		
		# If no items are being borrowed, stop here.
		if len(selected_items) == 0:
			messages.error(self.request, "No items were selected for borrowing.")
			return self.render_revalidation_failure("select", kwargs.get("form_dict")["select"])
		
		# We are borrowing items: Create the new Borrower Details object
		new_borrower_details = BorrowerDetails.objects.create(
			is_external=False,
			internal_member=cleaned_data["member"],
			borrower_name=cleaned_data["member"].long_name,
			borrower_address=cleaned_data["address"],
			borrower_phone=cleaned_data["phone_number"],
			borrow_authorised_by=self.request.user.member.long_name,
		)
		
		# Attach the new details to the reservation,
		# and is_active to False so that new items don't
		# get borrowed with it.
		reservation.borrower = new_borrower_details
		reservation.is_active = False
		reservation.save()
		
		# Create the Borrow Records for the items that are being borrowed.
		borrowed_items = []
		for item in selected_items:
			BorrowRecord.objects.create(
				item=item,
				borrower=new_borrower_details,
				due_date=reservation.requested_date_to_return,
			)
			borrowed_items.append((item, reservation.requested_date_to_return))
		send_borrow_receipt(
			email_address=cleaned_data["member"].email,
			borrower_name=cleaned_data["member"].long_name,
			items=borrowed_items,
			authorised_by=self.request.user.member.long_name
		)
		
		messages.success(self.request, f"The items were successfully borrowed!")
		return redirect("library:dashboard")


@method_decorator(gatekeeper_required, name="dispatch")
class ExternalReservationBorrowItemsWizard(SessionWizardView):
	"""
	This view handles the borrowing of Library Items in a "wizard", which is
	multiple forms working together in one view.
	This Wizard handles borrowing an Internal Reservation.
	"""
	form_list = [
		("select", ReservationSelectItemsFormset),
		("external_details", ExternalBorrowerDetailsForm),
	]
	template_name = "library/library_reservation_borrow_wizard.html"
	
	def get_reservation(self):
		reservation = get_object_or_404(Reservation, pk=self.kwargs["pk"])
		if not reservation.is_active:
			raise Http404("The requested reservation is not active.")
		if reservation.requested_date_to_borrow != datetime.date.today():
			raise Http404("The requested reservation is not for borrowing today.")
		if not reservation.is_external:
			raise Http404("The requested reservation is an internal reservation.")
		return reservation
	
	def render_goto_step(self, *args, **kwargs):
		"""
		This method overrides the WizardView Method.
		When going back a step, it allows the form to validate data that you may have already entered.
		If so, then it saves that data, so that when you return to that step, your data will be safe.
		"""
		form = self.get_form(data=self.request.POST, files=self.request.FILES)
		if form.is_valid():
			self.storage.set_step_data(self.steps.current, self.process_step(form))
			self.storage.set_step_files(self.steps.current, self.process_step_files(form))
		return super().render_goto_step(*args, **kwargs)
	
	def get_form_initial(self, step):
		"""
		This method overrides the WizardView method.
		Initialises the due date information for the chosen reservation.
		"""
		if step == "select":
			initial_form_data = []
			reservation = self.get_reservation()
			for item in reservation.reserved_items.all():
				availability_info = item.get_availability_info()
				if availability_info["in_clubroom"]:
					initial_form_data.append(
						{
							"item": item,
							"due_date": reservation.requested_date_to_return,
							"selected": False,
						}
					)
			return initial_form_data
		return super().get_form_initial(step)
	
	def done(self, form_list, **kwargs):
		"""
		When the form is submitted entirely, we first validate that no manipulation has occurred.
		Then we create the BorrowingRecords and all related objects.
		This includes:
			- Creating a new BorrowerDetails object
			- Create a new BorrowRecord object for each Item being borrowed.
			- Email the borrower a receipt.
		"""
		reservation = self.get_reservation()
		cleaned_data = self.get_all_cleaned_data()
		
		# Verify that each item from Step 1 is actually part of the reservation,
		# and determine which items are being borrowed now.
		
		selected_items = []
		for selected_item_form in cleaned_data["formset-select"]:
			if selected_item_form["item"] not in reservation.reserved_items.all():
				raise SuspiciousOperation("Item data has been tampered with or is missing.")
			else:
				if selected_item_form["selected"] is True:
					selected_items.append(selected_item_form["item"])
		
		# If no items are being borrowed, stop here.
		if len(selected_items) == 0:
			messages.error(self.request, "No items were selected for borrowing.")
			return self.render_revalidation_failure("select", kwargs.get("form_dict")["select"])
		
		# We are borrowing items: Create the new Borrower Details object
		new_borrower_details = BorrowerDetails.objects.create(
			is_external=True,
			internal_member=None,
			borrower_name=cleaned_data["borrower_name"],
			borrower_address=cleaned_data["address"],
			borrower_phone=cleaned_data["phone_number"],
			borrow_authorised_by=self.request.user.member.long_name,
		)
		
		# Attach the new details to the reservation,
		# and is_active to False so that new items don't
		# get borrowed with it.
		reservation.borrower = new_borrower_details
		reservation.is_active = False
		reservation.save()
		
		# Create the Borrow Records for the items that are being borrowed.
		borrowed_items = []
		for item in selected_items:
			BorrowRecord.objects.create(
				item=item,
				borrower=new_borrower_details,
				due_date=reservation.requested_date_to_return,
			)
			borrowed_items.append((item, reservation.requested_date_to_return))
		send_borrow_receipt(
			email_address=reservation.requestor_email,
			borrower_name=cleaned_data["borrower_name"],
			items=borrowed_items,
			authorised_by=self.request.user.member.long_name
		)
		
		messages.success(self.request, f"The items were successfully borrowed!")
		return redirect("library:dashboard")

