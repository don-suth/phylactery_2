from django.core.exceptions import SuspiciousOperation
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator
from formtools.wizard.views import SessionWizardView
from .decorators import gatekeeper_required
from .forms import (
	FresherMembershipForm,
	StaleMembershipForm,
	LegacyMembershipForm,
	MembershipFormPreview,
	AddFinanceRecordForm,
)
from .models import Member, Membership, FinanceRecord
from accounts.models import create_fresh_unigames_user
from blog.models import MailingList
from phylactery.communication.discord import send_to_operations


@method_decorator(gatekeeper_required, name="dispatch")
class FresherMembershipWizard(SessionWizardView):
	"""
	This view handles the Membership form in a "Wizard", which is multiple forms working together in one view.
	This view is used to handle Fresher Memberships - people that haven't signed up to the club before ever.
	"""
	form_list = [
		("0", FresherMembershipForm,),
		("preview", MembershipFormPreview,),
	]
	template_name = "members/membership_form.html"
	
	def get(self, request, *args, **kwargs):
		"""
		This overrides the superclass GET method entirely.
		Reasons:
			- We call all the original GET code anyway.
			- This allows us to generate a reference code and put it in storage.
			- It's only used when the member pays via bank transfer, but it means
				the code won't change when the member changes pages.
		"""
		
		# Original GET code
		self.storage.reset()
		self.storage.current_step = self.steps.first
		
		# Generate a new reference code, and put it in storage.
		self.storage.extra_data.update({"reference_code": FinanceRecord.objects.generate_code()})
		
		# Render form as usual.
		return self.render(self.get_form())
	
	def get_form_initial(self, step):
		"""
		Populates the reference code in the payment section.
		"""
		initial = super().get_form_initial(step)
		if step == "preview":
			initial["reference_code"] = self.storage.extra_data.get("reference_code")
		return initial
	
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
	
	def get_context_data(self, form, **kwargs):
		"""
		This method overrides the WizardView Method.
		For the "preview" step, we add the cleaned data from the previous steps
		into the context, so we can render the preview.
		"""
		context = super().get_context_data(form=form, **kwargs)
		if self.steps.current == "preview":
			context["preview_data"] = self.get_all_cleaned_data()
			context["preview_data"]["mailing_lists"] = []
			for mailing_list in MailingList.objects.filter(is_active=True):
				if context["preview_data"][f"mailing_list_{mailing_list.pk}"] is True:
					context["preview_data"]["mailing_lists"].append(mailing_list.name)
		return context
	
	def done(self, form_list, **kwargs):
		"""
		When the form is submitted entirely, we can create the new Member and all relevant details.
		This involves:
			- Creating a new Member object for them.
			- Attaching them to the Mailing Lists they chose.
			- Creating a new Membership object for them.
			- Creating a new UnigamesUser object for them.
			- TODO: Send them a Welcome email.
		"""
		cleaned_data = self.get_all_cleaned_data()
		
		# Create new UnigamesUser object
		new_user = create_fresh_unigames_user(email_address=cleaned_data.get("email_address"))
		
		# Allowance for the Legacy form here:
		if cleaned_data.get("approx_join_date") is not None:
			join_date = cleaned_data.get("approx_join_date")
		else:
			join_date = timezone.now()
		
		# Create new Member object
		new_member = Member.objects.create(
			short_name=cleaned_data.get("short_name"),
			long_name=cleaned_data.get("long_name"),
			pronouns=cleaned_data.get("pronouns"),
			student_number=cleaned_data.get("student_number"),
			join_date=join_date,
			optional_emails=cleaned_data.get("optional_emails"),
			user=new_user,
		)
		new_member.save()
		
		# Create new Membership
		amount_paid = 7
		if cleaned_data.get("is_guild") is True:
			amount_paid = 5
		
		new_membership = Membership.objects.create(
			member=new_member,
			date_purchased=timezone.now(),
			guild_member=cleaned_data.get("is_guild"),
			amount_paid=amount_paid,
			payment_method=cleaned_data.get("payment_method"),
			expired=False,
			authorised_by=self.request.unigames_member
		)
		new_membership.save()
		
		# Attach to the chosen mailing lists.
		for form_field, pk in form_list[0].extra_fields.items():
			if cleaned_data.get(form_field) is True:
				new_member.mailing_lists.add(pk)
		
		# If they paid with a transfer, add in the reference code
		if cleaned_data.get("payment_method") == "TFER":
			FinanceRecord.objects.create(
				member=new_member,
				purchase_type="Membership",
				reference_code=cleaned_data.get("reference_code"),
				amount=amount_paid,
				added_by=self.request.unigames_member,
				resolved=False,
			)
		
		# TODO: Email the new Member with a welcome email.
		
		messages.success(
			self.request,
			f"Membership for {cleaned_data.get('long_name')} was successfully created!"
		)
		
		return redirect("members:signup_hub")


@method_decorator(gatekeeper_required, name="dispatch")
class StaleMembershipWizard(FresherMembershipWizard):
	form_list = [
		("0", StaleMembershipForm,),
		("preview", MembershipFormPreview,),
	]
	stale_member = None
	
	def get(self, request, *args, **kwargs):
		"""
		This overrides the superclass GET method entirely.
		Reasons:
			- We call all the original GET code anyway.
			- This allows us to hook up the requested stale member into internal storage.
			- We also generate a reference code for paying via bank transfer.
		We also override the POST method as well below.
		"""
		
		stale_member = get_object_or_404(Member, pk=self.kwargs['pk'])
		self.stale_member = stale_member
		
		if stale_member.has_purchased_membership_this_year():
			# Protect members from purchasing a Membership they don't need.
			messages.info(
				request,
				f"{stale_member.short_name} has already purchased a Membership this year"
				f" - no need to buy another!"
			)
			return redirect("members:signup_hub")
		most_recent_membership = stale_member.get_most_recent_membership()
		if most_recent_membership is None or most_recent_membership.date_purchased.year < 2024:
			# Give a warning to Members who have not updated details since the short/long name migration.
			messages.warning(
				request,
				f"Welcome back! Unigames has changed how we store names. "
				f"Please pay particular attention to the Short name and Long name fields. Thanks!"
			)
		# Original GET code
		self.storage.reset()
		self.storage.current_step = self.steps.first
		
		# Put the pk of the member in storage for tamper detection.
		self.storage.extra_data.update({"stale_member": stale_member.pk})
		
		# Generate a new reference code, and put it in storage.
		self.storage.extra_data.update({"reference_code": FinanceRecord.objects.generate_code()})
		
		# Render form as usual
		return self.render(self.get_form())
	
	def post(self, *args, **kwargs):
		"""
		Overriding the POST method allows us to do a few extra checks:
			- First, we pull the pk out of storage (it's put there in the GET).
			- Second, if it's None or is different from the one in the URL, we raise a SuspiciousOperation.
			- Third, we pull out the appropriate member and put it in self.stale_member
			- Finally, we send it back to the original POST method.
		"""
		pk = self.storage.extra_data.get("stale_member")
		
		if pk is None or pk != self.kwargs["pk"]:
			# Something has gone wrong, either Maliciously or otherwise.
			raise SuspiciousOperation("Member data has been tampered with or is missing.")
		
		self.stale_member = get_object_or_404(Member, pk=pk)
		return super().post(*args, **kwargs)
	
	def get_form_initial(self, step):
		"""
		Populates the initial data of the form with the Member's current data.
		"""
		initial = super().get_form_initial(step)
		if self.stale_member is not None:
			initial["short_name"] = self.stale_member.short_name
			initial["long_name"] = self.stale_member.long_name
			initial["pronouns"] = self.stale_member.pronouns
			initial["email_address"] = self.stale_member.user.email
			initial["student_number"] = self.stale_member.student_number
			initial["optional_emails"] = self.stale_member.optional_emails
			if self.stale_member.student_number:
				initial["is_student"] = True
			else:
				initial["is_student"] = False
			if (recent_membership := self.stale_member.get_most_recent_membership()) is not None:
				initial["is_guild"] = recent_membership.guild_member
			else:
				initial["is_guild"] = False
			for mailing_list_pk in self.stale_member.mailing_lists.filter(is_active=True).values_list('pk', flat=True):
				initial[f"mailing_list_{mailing_list_pk}"] = True
		
		# Populate the reference code from storage
		if step == "preview":
			initial["reference_code"] = self.storage.extra_data.get("reference_code")
		
		return initial
	
	def get_context_data(self, form, **kwargs):
		"""
		Add in the data that has changed to the context to show on the preview panel.
		"""
		context = super().get_context_data(form=form, **kwargs)
		if self.steps.current == "preview":
			initial_data = self.get_form_initial("0")
			cleaned_data = self.get_cleaned_data_for_step("0")
			changes = []
			for field_name in [
				"short_name", "long_name",
				"pronouns", "email_address",
				"student_number", "optional_emails",
				"is_student", "is_guild"
			]:
				if initial_data[field_name] != cleaned_data.get(field_name):
					changes.append(field_name)
			if changes:
				context["initial"] = initial_data
				context["changes"] = changes
		return context
	
	def done(self, form_list, **kwargs):
		"""
		When the Stale membership form is submitted entirely, we need to:
			- Updating their email on their UnigamesUser.
			- Updating their Member details.
			- Attaching them to the Mailing Lists they chose.
			- Unattaching them from the Mailing Lists they didn't choose.
			- Creating a new Membership object for them.
			- TODO: Send them a receipt email.
		"""
		cleaned_data = self.get_all_cleaned_data()
		
		if self.stale_member.user is None:
			# Create a fresh UnigamesUser for them.
			self.stale_member.user = create_fresh_unigames_user(cleaned_data["email_address"])
		else:
			# Else we update email on their UnigamesUser
			self.stale_member.user.email = cleaned_data.get("email_address")
		self.stale_member.user.save()
		
		# Update Member details
		self.stale_member.short_name = cleaned_data.get("short_name")
		self.stale_member.long_name = cleaned_data.get("long_name")
		self.stale_member.pronouns = cleaned_data.get("pronouns")
		self.stale_member.student_number = cleaned_data.get("student_number")
		self.stale_member.optional_emails = cleaned_data.get("optional_emails")
		self.stale_member.save()
		
		# Attach / Unattach from mailing lists.
		for form_field, pk in form_list[0].extra_fields.items():
			if cleaned_data.get(form_field) is True:
				self.stale_member.mailing_lists.add(pk)
			else:
				self.stale_member.mailing_lists.remove(pk)
		
		# Create a new Membership.
		amount_paid = 7
		if cleaned_data.get("is_guild") is True:
			amount_paid = 5
		
		new_membership = Membership.objects.create(
			member=self.stale_member,
			date_purchased=timezone.now(),
			guild_member=cleaned_data.get("is_guild"),
			amount_paid=amount_paid,
			payment_method=cleaned_data.get("payment_method"),
			expired=False,
			authorised_by=self.request.unigames_member
		)
		new_membership.save()
		
		# If they paid with a transfer, add in the reference code
		if cleaned_data.get("payment_method") == "TFER":
			FinanceRecord.objects.create(
				member=self.stale_member,
				purchase_type="Membership",
				reference_code=cleaned_data.get("reference_code"),
				amount=amount_paid,
				added_by=self.request.unigames_member,
				resolved=False,
			)
		
		# TODO: Send receipt email
		
		messages.success(
			self.request,
			f"Membership for {cleaned_data.get('long_name')} was successfully created!"
		)
		
		return redirect("members:signup_hub")


class LegacyMembershipWizard(FresherMembershipWizard):
	form_list = [
		("0", LegacyMembershipForm,),
		("preview", MembershipFormPreview,),
	]


@method_decorator(gatekeeper_required, name="dispatch")
class FinanceRecordWizard(SessionWizardView):
	"""
	A wizard to handle a manual entry of a FinanceRecord.
	This enables us to save the generated code in storage,
	otherwise it would be randomly generated each time.
	"""
	
	form_list = [
		("0", AddFinanceRecordForm,),
	]
	
	template_name = "members/finance_form.html"
	
	def get(self, request, *args, **kwargs):
		"""
		This overrides the superclass GET method entirely.
		Reasons:
			- We call all the original GET code anyway.
			- This allows us to generate a reference code and put it in storage.
			- It's only used when the member pays via bank transfer, but it means
				the code won't change when the member changes pages.
		"""
		
		# Original GET code
		self.storage.reset()
		self.storage.current_step = self.steps.first
		
		# Generate a new reference code, and put it in storage.
		self.storage.extra_data.update({"reference_code": FinanceRecord.objects.generate_code()})
		
		# Render form as usual.
		return self.render(self.get_form())
	
	def get_form_initial(self, step):
		"""
		Populates the reference code in the payment section.
		"""
		initial = super().get_form_initial(step)
		if step == "0":
			initial["reference_code"] = self.storage.extra_data.get("reference_code")
		return initial
	
	def done(self, form_list, **kwargs):
		cleaned_data = self.get_all_cleaned_data()
		FinanceRecord.objects.create(
			member=cleaned_data.get("member"),
			purchase_type=cleaned_data.get("description"),
			reference_code=cleaned_data.get("reference_code"),
			amount=cleaned_data.get("amount"),
			added_by=self.request.unigames_member,
			resolved=False,
		)
		
		messages.success(
			self.request,
			f"Successfully added finance record for {cleaned_data.get('member')} "
			f"with code {cleaned_data.get('reference_code')}."
		)
		
		return redirect("members:finance_record")
