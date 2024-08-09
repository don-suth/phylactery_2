import datetime
from dal import autocomplete
from django import forms
from django.contrib import messages
from django.utils.text import slugify
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field
from crispy_forms.bootstrap import Accordion, AccordionGroup
from members.models import Member, Rank, RankChoices, Membership


def expire_active_ranks(rank_to_expire, rank_to_exclude):
	"""
	Finds all ranks of the chosen type that are still active, and expires them.
	Ignores all ranks belonging to members that also have rank_to_exclude.
	Returns the names of Members with Ranks expired this way.
	"""
	members_to_exclude = Rank.objects.all_active().filter(rank_name=rank_to_exclude).values_list("member", flat=True)
	ranks_to_expire = Rank.objects.all_active().filter(rank_name=rank_to_expire).exclude(member__in=members_to_exclude)
	expired_members = list(ranks_to_expire.values_list("member__long_name", flat=True))
	for rank in ranks_to_expire:
		rank.set_expired()
	return expired_members


class ControlPanelForm(forms.Form):
	"""
	Base class for a Control Panel Form
	
	Subclasses must define the following:
		Attributes:
			form_name:
				Human-readable name for the form.
				Will be displayed in the list view and detail view.
				The slug value of the form_name will also be used internally.
			form_short_description:
				Human-readable short description of what the form does.
				Will be displayed in the list view.
			form_long_description:
				Optional human-readable long description of what the form does.
				If not provided, the short description will be used instead.
				Will be displayed only in the detail view.
			form_allowed_ranks:
				A whitelist of ranks that are allowed to access the form.
		
		Methods:
			get_layout(self):
				Returns the Crispy layout used for the form.
			submit(self, request):
				Processes the form.
	"""
	
	form_name: str | None = None
	form_short_description: str | None = None
	form_long_description: str | None = None
	form_allowed_ranks: list = []
	form_include_media = True
	
	form_confirm_field = forms.BooleanField(
		label="I confirm I wish to perform this action.",
		initial=False,
		required=True,
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		if self.form_name is None:
			raise NotImplemented
		if self.form_short_description is None:
			raise NotImplemented
		if self.form_long_description is None:
			self.form_long_description = self.form_short_description
		
		self.slug_name = slugify(self.form_name)
		self.prefix = self.slug_name
		
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.include_media = self.form_include_media
		
		self.helper.layout = self.get_layout()
	
	def get_layout(self):
		raise NotImplemented
	
	def submit(self, request):
		raise NotImplemented
	

class GatekeeperWebkeeperPurgeForm(ControlPanelForm):
	form_name = "Purge Gatekeepers / Webkeepers"
	form_short_description = "Expire the Gatekeeper and/or Webkeeper rank of all non-Committee members."
	form_allowed_ranks = [
		RankChoices.PRESIDENT,
		RankChoices.VICEPRESIDENT,
		RankChoices.SECRETARY,
		RankChoices.WEBKEEPER,
	]
	
	CHOICES = (
		("gatekeeper", "Gatekeepers only"),
		("webkeeper", "Webkeepers only"),
		("both", "Both Gatekeepers and Webkeepers")
	)
	
	purge_choice = forms.ChoiceField(
		choices=CHOICES,
		label="Purge the status of:",
		widget=forms.RadioSelect(),
		required=True,
	)
	
	def get_layout(self):
		return Layout(
			Field("purge_choice"),
		)
	
	def submit(self, request):
		if self.is_valid():
			purge_choice = self.cleaned_data["purge_choice"]
			if purge_choice in ["gatekeeper", "both"]:
				purged_gate = expire_active_ranks(
					rank_to_expire=RankChoices.GATEKEEPER,
					rank_to_exclude=RankChoices.COMMITTEE
				)
				if len(purged_gate) > 0:
					messages.success(
						request,
						message=f"Removed Gatekeeper from {len(purged_gate)} members: "
						f"{', '.join(purged_gate)}"
					)
				else:
					messages.warning(
						request,
						message="No non-committee gatekeepers to remove."
					)
			if purge_choice in ["webkeeper", "both"]:
				purged_web = expire_active_ranks(
					rank_to_expire=RankChoices.WEBKEEPER,
					rank_to_exclude=RankChoices.COMMITTEE
				)
				if len(purged_web) > 0:
					messages.success(
						request,
						message=f"Removed Webkeeper from {len(purged_web)} members: "
						f"{', '.join(purged_web)}"
					)
				else:
					messages.warning(
						request,
						message="No non-committee gatekeepers to remove."
					)


class ExpireMembershipsForm(ControlPanelForm):
	form_name = "Invalidate Memberships"
	form_short_description = "Expires any active memberships purchased before a given date."
	form_allowed_ranks = [
		RankChoices.PRESIDENT,
		RankChoices.VICEPRESIDENT,
		RankChoices.SECRETARY,
		RankChoices.WEBKEEPER,
	]
	
	cut_off_date = forms.DateField(
		label="Invalidate memberships purchased before:",
		required=True,
		widget=forms.DateInput(
			attrs={
				"type": "date"
			}
		),
		initial=datetime.date.today().strftime("%Y-01-01"),
	)
	
	def get_layout(self):
		return Layout(
			Field("cut_off_date"),
		)
	
	def clean_cut_off_date(self):
		today = datetime.date.today()
		cut_off_date = self.cleaned_data["cut_off_date"]
		if cut_off_date > today:
			raise forms.ValidationError("Date cannot be in the future.")
		return cut_off_date
	
	def submit(self, request):
		if self.is_valid():
			memberships_to_expire = Membership.objects.filter(
				date_purchased__lt=self.cleaned_data["cut_off_date"],
				expired=False
			)
			if memberships_to_expire.exists():
				number_of_expired_memberships = memberships_to_expire.count()
				for membership in memberships_to_expire:
					membership.expired = True
					membership.save()
				messages.success(
					request,
					f"Successfully invalidated {number_of_expired_memberships} membership{'s' if number_of_expired_memberships > 1 else ''}."
				)
			else:
				messages.warning(
					request,
					"No memberships to expire."
				)


class MakeGatekeepersForm(ControlPanelForm):
	form_name = "Promote Members to Gatekeepers"
	form_short_description = "Promotes the selected members to Gatekeepers."
	form_allowed_ranks = [
		RankChoices.PRESIDENT,
		RankChoices.VICEPRESIDENT,
		RankChoices.SECRETARY,
		RankChoices.WEBKEEPER,
	]
	form_include_media = False
	
	gatekeepers_to_add = forms.ModelMultipleChoiceField(
		queryset=Member.objects.all(),
		widget=autocomplete.ModelSelect2Multiple(
			url="members:autocomplete_member",
			attrs={
				"data-theme": "bootstrap-5"
			}
		)
	)
	
	def get_layout(self):
		return Layout(
			"gatekeepers_to_add"
		)
	
	def submit(self, request):
		# TODO: Test this
		if self.is_valid():
			already_gatekeepers = []
			success_gatekeepers = []
			for member in self.cleaned_data["gatekeepers_to_add"]:
				if member.is_gatekeeper():
					already_gatekeepers.append(member.long_name)
				else:
					member.add_rank(RankChoices.GATEKEEPER)
					success_gatekeepers.append(member.long_name)
			if already_gatekeepers:
				messages.warning(
					request,
					f"The following members were already Gatekeepers. "
					f"They have been skipped: {', '.join(already_gatekeepers)}"
				)
			if success_gatekeepers:
				messages.success(
					request,
					f"The following members were successfully made Gatekeepers: "
					f"{', '.join(success_gatekeepers)}"
				)


class MakeWebkeepersForm(ControlPanelForm):
	form_name = "Promote Members to Webkeepers"
	form_short_description = "Promotes the selected members to Webkeepers."
	form_allowed_ranks = [
		RankChoices.PRESIDENT,
		RankChoices.VICEPRESIDENT,
		RankChoices.SECRETARY,
		RankChoices.WEBKEEPER,
	]
	form_include_media = False
	
	webkeepers_to_add = forms.ModelMultipleChoiceField(
		queryset=Member.objects.all(),
		widget=autocomplete.ModelSelect2Multiple(
			url="members:autocomplete_member",
			attrs={
				"data-theme": "bootstrap-5"
			}
		)
	)
	
	def get_layout(self):
		return Layout(
			"webkeepers_to_add"
		)
	
	def submit(self, request):
		if self.is_valid():
			already_webkeepers = []
			success_webkeepers = []
			for member in self.cleaned_data["webkeepers_to_add"]:
				if member.is_webkeeper():
					already_webkeepers.append(member.long_name)
				else:
					member.add_rank(RankChoices.WEBKEEPER)
					success_webkeepers.append(member.long_name)
			if already_webkeepers:
				messages.warning(
					request,
					f"The following members were already Webkeepers. "
					f"They have been skipped: {', '.join(already_webkeepers)}"
				)
			if success_webkeepers:
				messages.success(
					request,
					f"The following members were successfully made Webkeepers: "
					f"{', '.join(success_webkeepers)}"
				)


class AddRemoveRanksForm(ControlPanelForm):
	form_name = "Selectively Add or Remove Ranks"
	form_short_description = (
		"Adds or Removes ranks for a single member. "
		"Useful for removing the Gatekeeper rank or adding the Excluded rank to a single member."
	)
	form_long_description = (
		"This form cannot be used for Committee Rank transferal. "
		"Use the Committee Transfer Form for that."
	)
	form_allowed_ranks = [
		RankChoices.PRESIDENT,
		RankChoices.VICEPRESIDENT,
		RankChoices.SECRETARY,
		RankChoices.WEBKEEPER,
	]
	form_include_media = False
	
	member_to_alter = forms.ModelChoiceField(
		queryset=Member.objects.all(),
		widget=autocomplete.ModelSelect2(
			url="members:autocomplete_member",
			attrs={
				"data-theme": "bootstrap-5"
			}
		)
	)
	operation = forms.ChoiceField(
		choices=[
			("ADD", "Add Rank"),
			("REMOVE", "Remove Rank"),
		],
		widget=forms.RadioSelect
	)
	rank_to_alter = forms.ChoiceField(
		choices=[
			(RankChoices.GATEKEEPER.name, RankChoices.GATEKEEPER.label),
			(RankChoices.WEBKEEPER.name, RankChoices.WEBKEEPER.label),
			(RankChoices.EXCLUDED.name, RankChoices.EXCLUDED.label),
			(RankChoices.LIFEMEMBER.name, RankChoices.LIFEMEMBER.label),
		]
	)
	
	def get_layout(self):
		return Layout(
			"member_to_alter",
			"operation",
			"rank_to_alter"
		)
	
	def submit(self, request):
		if self.is_valid():
			cleaned_member = self.cleaned_data["member_to_alter"]
			cleaned_operation = self.cleaned_data["operation"]
			cleaned_rank = self.cleaned_data["rank_to_alter"]
			cleaned_rank_label = dict(self.fields["rank_to_alter"].choices)[cleaned_rank]
			if cleaned_operation == "ADD":
				if cleaned_member.has_rank(cleaned_rank):
					messages.warning(
						request,
						f"{cleaned_member.long_name} is already {cleaned_rank_label}."
					)
				else:
					cleaned_member.add_rank(cleaned_rank)
					messages.success(
						request,
						f"{cleaned_member.long_name} was successfully made {cleaned_rank_label}."
					)
			elif cleaned_operation == "REMOVE":
				ranks_to_expire = Rank.objects.all_active().filter(
					member=cleaned_member,
					rank_name=cleaned_rank,
				)
				if ranks_to_expire.count() > 0:
					for rank in ranks_to_expire:
						rank.set_expired()
					messages.success(
						request,
						f"Successfully expired all {cleaned_rank_label} ranks from {cleaned_member.long_name}."
					)
				else:
					messages.warning(
						request,
						f"{cleaned_member.long_name} does not have an active {cleaned_rank_label} rank."
					)


class CommitteeTransferForm(ControlPanelForm):
	form_name = "Committee Transfer"
	form_short_description = "Freely transfer committee roles."
	form_allowed_ranks = [
		RankChoices.PRESIDENT,
		RankChoices.VICEPRESIDENT,
		RankChoices.WEBKEEPER,
	]
	form_include_media = False
	
	NUMBER_OF_OCMS = 4
	
	RADIO_CHOICES = [
		("retain", "Retain previous committee member"),
		("elect", "Elect new committee member"),
		("remove", "Remove the committee member from this position, with no replacement"),
	]
	
	COMMITTEE_POSITIONS = [
		RankChoices.PRESIDENT,
		RankChoices.VICEPRESIDENT,
		RankChoices.TREASURER,
		RankChoices.SECRETARY,
		RankChoices.LIBRARIAN,
		RankChoices.FRESHERREP,
		RankChoices.OCM,
		RankChoices.IPP,
	]
	
	def get_field_names(self):
		field_names = {}
		for position in self.COMMITTEE_POSITIONS:
			field_names[position] = []
			if position == "OCM":
				for i in range(self.NUMBER_OF_OCMS):
					assigned_field_name = f"assigned_{slugify(position)}_{i+1}"
					options_field_name = f"options_{slugify(position)}_{i+1}"
					field_names[position].append((assigned_field_name, options_field_name))
			else:
				assigned_field_name = f"assigned_{slugify(position)}"
				options_field_name = f"options_{slugify(position)}"
				field_names[position].append((assigned_field_name, options_field_name))
		return field_names
	
	def check_valid_for_position(self, field, member, position):
		EXEC_POSITIONS = [
			RankChoices.PRESIDENT,
			RankChoices.VICEPRESIDENT,
			RankChoices.TREASURER,
			RankChoices.SECRETARY,
			RankChoices.LIBRARIAN,
		]
		if member is None:
			self.add_error(field, "You haven't selected anyone to elect to this position.")
			return False
		if not member.has_active_membership():
			self.add_error(field, "This member doesn't have a valid membership.")
			return False
		if member.student_number == "" or member.student_number is None:
			self.add_error(field, "This member doesn't appear to be a student. (No student number recorded.)")
			return False
		if member.has_rank(RankChoices.EXCLUDED):
			self.add_error(field, "This member is currently excluded.")
			return False
		if position in EXEC_POSITIONS and member.get_most_recent_membership().guild_member is False:
			self.add_error(field, "This member is not currently a Guild member.")
			return False
		return True
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		field_names = self.get_field_names()
		current_ocm_number = 0
		current_committee = Rank.objects.get_committee()
		for position in field_names:
			for field_name in field_names[position]:
				if field_name.startswith("assigned"):
					if position.label == "OCM":
						position_initial = current_committee[position][current_ocm_number].member
						field_label = f"Assigned {position.label} #{current_ocm_number+1}"
						current_ocm_number += 1
					else:
						position_initial = current_committee[position][0].member
						field_label = f"Assigned {position.label}"
					self.fields[field_name] = forms.ModelChoiceField(
						label=field_label,
						queryset=Member.objects.all(),
						widget=autocomplete.ModelSelect2(
							url="members:autocomplete_member",
							attrs={
								"data-theme": "bootstrap-5"
							}
						),
						initial=position_initial
					)
				else:
					self.fields[field_name] = forms.ChoiceField(
						widget=forms.RadioSelect,
						choices=self.RADIO_CHOICES,
						label="",
						initial="retain"
					)
		
	def get_layout(self):
		accordion = Accordion()
		field_names = self.get_field_names()
		for position in field_names:
			accordion.append(
				AccordionGroup(
					position.label,
					*field_names[position]
				)
			)
		return Layout(
			accordion
		)
	
	def clean(self):
		new_committee = {}
		old_committee = Rank.objects.get_committee()
		field_names = self.get_field_names()
		
		for position in self.COMMITTEE_POSITIONS:
			if position != RankChoices.OCM:
				assigned_field_name = field_names[position][0]
				options_field_name = field_names[position][1]
				cleaned_assigned_member = self.cleaned_data[assigned_field_name]
				cleaned_options = self.cleaned_data[options_field_name]
				
				match cleaned_options:
					case "retain":
						# Check for a data entry error
						if cleaned_assigned_member == old_committee[position][0]:
							# Recheck eligibility - errors will be added if they aren't.
							if self.check_valid_for_position(
									assigned_field_name,
									cleaned_assigned_member,
									position
							):
								# They are eligible - add them in!
								new_committee[position] = list(cleaned_assigned_member)
						else:
							# Warn the user of a potential data entry error.
							self.add_error(assigned_field_name, "")
							self.add_error(options_field_name, "You selected 'Retain', but also selected a different member for this position. Did you make a mistake?")
					case "remove":
						# No person is being assigned to this position.
						new_committee[position] = list()
					case "elect":
						# Check eligibility
						if self.check_valid_for_position(
							assigned_field_name,
							cleaned_assigned_member,
							position,
						):
							# They are eligible, let them in
							new_committee[position] = list(cleaned_assigned_member)
				
				
				
	
	def submit(self, request):
		if self.is_valid():
			pass
	
	


class GetMembershipInfoForm(ControlPanelForm):
	form_name = "Get Membership CSV"
	form_short_description = "Get a CSV of membership data for a particular date. Useful for O-Day information."
	form_long_description = (
		"This will output a CSV containing the name, student number, and guild status "
		"of each membership purchased on the selected date."
	)
	form_allowed_ranks = [
		RankChoices.COMMITTEE,
		RankChoices.WEBKEEPER,
	]
	
	def get_layout(self):
		return Layout()
	
	

FORM_CLASSES = {}
for form_class in (
	GatekeeperWebkeeperPurgeForm,
	ExpireMembershipsForm,
	MakeGatekeepersForm,
	MakeWebkeepersForm,
	AddRemoveRanksForm,
	CommitteeTransferForm,
	GetMembershipInfoForm,
):
	FORM_CLASSES[slugify(form_class.form_name)] = form_class
