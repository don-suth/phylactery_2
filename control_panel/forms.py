import datetime
from dal import autocomplete
from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from colorfield.widgets import ColorWidget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field
from crispy_forms.bootstrap import Accordion, AccordionGroup
from members.models import Member, Rank, RankChoices, Membership
from phylactery.form_fields import HTML5DateInput
import csv
import redis


def expire_active_ranks(rank_to_expire, rank_to_exclude, delete=False):
	"""
	Finds all ranks of the chosen type that are still active, and expires them.
	Ignores all ranks belonging to members that also have rank_to_exclude.
	Returns the names of Members with Ranks expired this way.
	If delete = True, then deletes the ranks rather than expiring them.
	"""
	members_to_exclude = Rank.objects.all_active().filter(rank_name=rank_to_exclude).values_list("member", flat=True)
	ranks_to_expire = Rank.objects.all_active().filter(rank_name=rank_to_expire).exclude(member__in=members_to_exclude)
	expired_members = list(ranks_to_expire.values_list("member__long_name", flat=True))
	if delete:
		ranks_to_expire.delete()
	else:
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
		skip_layout = kwargs.pop("skip_layout", False)
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
		
		if skip_layout is False:
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
		RankChoices.SUPERUSER,
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
				purged_superusers = expire_active_ranks(
					rank_to_expire=RankChoices.SUPERUSER,
					rank_to_exclude=RankChoices.COMMITTEE,
					delete=True,
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
		RankChoices.SUPERUSER,
	]
	
	cut_off_date = forms.DateField(
		label="Invalidate memberships purchased before:",
		required=True,
		widget=HTML5DateInput(),
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
		RankChoices.SUPERUSER,
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
		if self.is_valid():
			already_gatekeepers = []
			success_gatekeepers = []
			for member in self.cleaned_data["gatekeepers_to_add"]:
				if member.has_rank(RankChoices.GATEKEEPER):
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
		RankChoices.SUPERUSER,
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
		RankChoices.SUPERUSER,
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
		RankChoices.SUPERUSER,
	]
	form_include_media = False
	
	NUMBER_OF_OCMS = 4
	
	RADIO_CHOICES = [
		("retain", "Retain previous committee member"),
		("elect", "Elect new committee member"),
		("remove", "Remove the committee member from this position, with no replacement"),
	]
	
	UNASSIGNED_RADIO_CHOICES = [
		("retain", "Keep this position unassigned"),
		("elect", "Elect new committee member"),
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
	
	def get_field_names_by_position(self):
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
		super().__init__(*args, skip_layout=True, **kwargs)
		
		field_names_by_position = self.get_field_names_by_position()
		current_ocm_number = 0
		current_committee = Rank.objects.get_committee()
		for position in field_names_by_position:
			for assigned_field_name, options_field_name in field_names_by_position[position]:
				if position == RankChoices.OCM:
					try:
						position_initial = current_committee[position][current_ocm_number].member
					except IndexError:
						position_initial = None
					field_label = f"Assigned {position.label} #{current_ocm_number+1}"
					current_ocm_number += 1
				else:
					try:
						position_initial = current_committee[position][0].member
					except IndexError:
						position_initial = None
					field_label = f"Assigned {position.label}"
				
				field_choices = self.RADIO_CHOICES
				field_required = True
				if position_initial is None:
					# Present a different set of choices if there's no member assigned
					field_choices = self.UNASSIGNED_RADIO_CHOICES
					field_required = False
				
				self.fields[assigned_field_name] = forms.ModelChoiceField(
						label=field_label,
						queryset=Member.objects.all(),
						widget=autocomplete.ModelSelect2(
							url="members:autocomplete_member",
							attrs={
								"data-theme": "bootstrap-5"
							}
						),
						initial=position_initial,
						required=field_required
					)
				
				self.fields[options_field_name] = forms.ChoiceField(
					widget=forms.RadioSelect,
					choices=field_choices,
					label="",
					initial="retain"
				)
		self.helper.layout = self.get_layout()
		self.cleaned_committee_changes = None

	def get_layout(self):
		accordion = Accordion()
		field_names_by_position = self.get_field_names_by_position()
		for position in field_names_by_position:
			accordion_group = AccordionGroup(position.label)
			for assigned_field, options_field in field_names_by_position[position]:
				if self.has_error(assigned_field) or self.has_error(options_field):
					accordion_group.active = True
				accordion_group.append(assigned_field)
				accordion_group.append(options_field)
			accordion.append(accordion_group)
		return Layout(
			accordion
		)
	
	def clean(self):
		"""
		Validates and compiles the committee changes into a list of changes.
		Each item in the list will be a tuple in the form of
		(<member>, <old_rank>, <new_rank>)
		
		If old_rank is None: They are new to committee.
		If new_rank is None: They are leaving committee.
		"""
		field_names_by_position = self.get_field_names_by_position()
		committee_to_remove = set()
		old_committee_by_position = Rank.objects.get_committee()
		old_committee_by_member = dict()
		new_committee_members = set()
		for old_position in old_committee_by_position:
			for rank_object in old_committee_by_position[old_position]:
				committee_to_remove.add(rank_object.member)
				old_committee_by_member[rank_object.member] = old_position
		
		committee_changes = list()
		
		for position in field_names_by_position:
			for assigned_field_name, options_field_name in field_names_by_position[position]:
				cleaned_assigned_member = self.cleaned_data[assigned_field_name]
				cleaned_option = self.cleaned_data[options_field_name]
				
				if cleaned_assigned_member is None:
					# Only valid option is "retain" in this case.
					if cleaned_option == "elect":
						self.add_error(
							assigned_field_name,
							"You selected 'elect', but no new committee member was selected for this position."
						)
					# Nothing else we need to do for this oen.
					continue
				
				if cleaned_assigned_member in new_committee_members and cleaned_option != "remove":
					# Check if there's any duplicates (provided we aren't removing this member.)
					self.add_error(assigned_field_name, f"Committee can't have duplicate members.")
				
				else:
					match cleaned_option:
						case "retain":
							# Check for a data entry error
							if assigned_field_name in self.changed_data:
								# Warn the user of a potential data entry error.
								self.add_error(assigned_field_name, "")
								self.add_error(
									options_field_name,
									"You selected 'No Changes', but also selected a different member for this position. "
									"Did you make a mistake?"
								)
							else:
								# Check if they're eligible. If not, then errors will be added automatically.
								if self.check_valid_for_position(assigned_field_name, cleaned_assigned_member, position):
									# They're valid! Put them in!
									new_committee_members.add(cleaned_assigned_member)
									committee_to_remove.discard(cleaned_assigned_member)
									old_position = old_committee_by_member.get(cleaned_assigned_member, None)
									committee_changes.append(
										(cleaned_assigned_member, old_position, position)
									)
						case "elect":
							# Check if they're eligible. If not, then errors will be added automatically.
							if self.check_valid_for_position(assigned_field_name, cleaned_assigned_member, position):
								# They're valid! Put them in!
								new_committee_members.add(cleaned_assigned_member)
								committee_to_remove.discard(cleaned_assigned_member)
								old_position = old_committee_by_member.get(cleaned_assigned_member, None)
								committee_changes.append(
									(cleaned_assigned_member, old_position, position)
								)
						case "remove":
							# Nothing to do here
							pass
		# Now, make sure all old committee members are removed.
		for old_committee_member in committee_to_remove:
			old_position = old_committee_by_member[old_committee_member]
			committee_changes.append(
				(old_committee_member, old_position, None)
			)
		self.cleaned_committee_changes = committee_changes

	def submit(self, request):
		self.clean()
		if self.is_valid():
			change_messages = []
			for change in self.cleaned_committee_changes:
				match change:
					case (member, None, new_position):
						# Add a committee rank, and their new position.
						member.add_rank(RankChoices.COMMITTEE)
						member.add_rank(new_position)
						change_messages.append(f"Added {member.long_name} to {new_position.label}.")
					case (member, old_position, None):
						# Expire their position and their committee rank.
						member.remove_rank(RankChoices.COMMITTEE)
						member.remove_rank(old_position)
						change_messages.append(f"Removed {member.long_name}.")
					case (member, old_position, new_position) if old_position == new_position:
						# Nothing we need to do.
						change_messages.append(f"{member.long_name} will continue to be {old_position.label}.")
					case (member, old_position, new_position):
						# Leave the committee position, expire their old position rank, and add the new one.
						member.remove_rank(old_position)
						member.add_rank(new_position)
						change_messages.append(f"{member.long_name} moved from {old_position.label} to {new_position.label}.")
			if change_messages:
				messages.success(request, "\n".join(change_messages))


class GetMembershipInfoForm(ControlPanelForm):
	form_name = "Get Membership CSV"
	form_short_description = "Get a CSV of membership data for a particular date. Useful for O-Day information."
	form_long_description = (
		"This will output a CSV containing the name, student number, and guild status "
		"of each membership purchased on the selected date."
	)
	form_allowed_ranks = [
		RankChoices.COMMITTEE,
		RankChoices.SUPERUSER,
	]
	
	membership_date = forms.DateField(
		label="Date of membership:",
		required=True,
		widget=HTML5DateInput(),
	)
	only_guild = forms.BooleanField(
		label="Only show memberships from Guild members?",
		required=False,
	)
	
	def get_layout(self):
		return Layout(
			"membership_date",
			"only_guild",
		)
	
	def clean_membership_date(self):
		today = timezone.localdate()
		cleaned_date = self.cleaned_data["membership_date"]
		if cleaned_date > today:
			raise forms.ValidationError("Date cannot be in the future.")
		return cleaned_date
	
	def submit(self, request):
		memberships = Membership.objects.filter(
			date_purchased=self.cleaned_data["membership_date"]
		)
		if self.cleaned_data["only_guild"]:
			memberships = memberships.filter(
				guild_member=True
			)
		if memberships.count() > 0:
			date_string = self.cleaned_data["membership_date"].isoformat()
			csv_data = memberships.values_list(
				"member__long_name",
				"member__student_number",
				"guild_member",
			)
			response = HttpResponse(
				content_type="text/csv",
				headers={
					"Content-Disposition": f'attachment; filename="{date_string}-memberships.csv"'
				}
			)
			writer = csv.writer(response)
			writer.writerow(["Name", "Student Number", "Guild"])
			writer.writerows(csv_data)
			return response
		else:
			messages.warning(request, "No memberships exist for the chosen date.")


class BaseRedisSettingsForm(ControlPanelForm):
	"""
	Base class for redis settings forms.
	"""
	REDIS_SETTINGS_KEY = ""
	
	def __init__(self, *args, **kwargs):
		"""
		This form is designed to easily set some settings stored in redis.
		This is done by:
			1) Connecting to the redis instance
			2) Loading a few special dicts (hashes) from redis, which are:
				- The base settings dict (stored in REDIS_SETTINGS_KEY), which stores key names and values
				- The field type dict (REDIS_SETTINGS_KEY:types), which stores the data type of each key
					- Valid types: string, colour, boolean
				- The help text dict (REDIS_SETTINGS_KEY:help), which stores the help text for each key.
				- The display text dict (REDIS_SETTINGS_KEY:display), which stores the display label for the key.
			3) For each key in that dict, check the current value of it:
				a) If it's a string, create a charfield
				b) If it's a colour, create a colour field.
				c) If it's a bool, create a choice field.
				d) If it's an int, create an integer field.
				e) Otherwise, don't create one (maybe display a warning?)
			4) Set the initial value of that field to the value of the key.
		"""
		super().__init__(*args, skip_layout=True, **kwargs)
		self.helper.layout = Layout()
		self.redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
		key_values_dict = self.redis_connection.hgetall(self.REDIS_SETTINGS_KEY)
		key_types_dict = self.redis_connection.hgetall(f"{self.REDIS_SETTINGS_KEY}:types")
		key_help_dict = self.redis_connection.hgetall(f"{self.REDIS_SETTINGS_KEY}:help")
		key_display_dict = self.redis_connection.hgetall(f"{self.REDIS_SETTINGS_KEY}:display")
		self.setting_fields = []
		for key, value in key_values_dict.items():
			key_type = key_types_dict[key]
			key_help = key_help_dict[key]
			key_display = key_display_dict[key]
			match key_type:
				case "string":
					self.setting_fields.append(key)
					self.fields[key] = forms.CharField(
						label=key_display,
						help_text=key_help,
						initial=value,
						required=True,
					)
					self.helper.layout.append(
						Field(
							key,
							wrapper_class="font-monospace"
						)
					)
				case "colour":
					self.setting_fields.append(key)
					self.fields[key] = forms.CharField(
						label=key_display,
						help_text=key_help,
						initial=value,
						required=True,
						widget=ColorWidget(attrs={"format": "rgb"})
					)
					self.helper.layout.append(
						Field(
							key,
							wrapper_class="font-monospace"
						)
					)
				case "boolean":
					self.setting_fields.append(key)
					self.fields[key] = forms.BooleanField(
						label=key_display,
						help_text=key_help,
						initial=bool(int(value)),
						required=False,
					)
					self.helper.layout.append(
						Field(
							key,
							wrapper_class="font-monospace"
						)
					)
				case "int":
					# Currently, we assume min=1, max=100.
					# This may change in the future.
					self.setting_fields.append(key)
					self.fields[key] = forms.IntegerField(
						label=key_display,
						help_text=key_help,
						initial=int(value),
						required=True,
						min_value=1,
						max_value=100,
					)
					self.helper.layout.append(
						Field(
							key,
							wrapper_class="font-monospace"
						)
					)
				
			
	def submit(self, request):
		"""
		On submitting:
			- Update each changed key in redis
			- If any keys were changed, ping a pubsub channel of the same name
		"""
		self.clean()
		if self.is_valid():
			change_messages = []
			for field_name in self.setting_fields:
				if field_name in self.changed_data:
					cleaned_field_data = self.cleaned_data[field_name]
					# If it's a boolean, change to an integer for storage in redis
					if type(cleaned_field_data) is bool:
						cleaned_field_data = int(cleaned_field_data)
					self.redis_connection.hset(self.REDIS_SETTINGS_KEY, field_name, cleaned_field_data)
					change_messages.append(f"Set key `{field_name}` to value '{cleaned_field_data}'")
			if change_messages:
				messages.success(request, "\n".join(change_messages))
				self.redis_connection.publish(self.REDIS_SETTINGS_KEY, "updated")


class DiscordSettingsForm(BaseRedisSettingsForm):
	form_name = "Discord Bot Settings"
	form_short_description = "Change various settings related to the Discord bot."
	form_long_description = (
		"Change various settings for the Discord bot, such as what channel notifications are sent to. "
		"You shouldn't need to adjust these settings too often."
	)
	form_allowed_ranks = [
		RankChoices.SUPERUSER,
	]
	
	REDIS_SETTINGS_KEY = "lich:settings"


class ClockSettingsForm(BaseRedisSettingsForm):
	form_name = "Clock Settings"
	form_short_description = "Change the appearance of the clock."
	form_long_description = (
		"Change the brightness and colour of the clock, and also whether the seconds indicator flashes."
	)
	form_allowed_ranks = [
		RankChoices.SUPERUSER,
	]
	
	REDIS_SETTINGS_KEY = "clock:settings"
	

class InitialiseRedisSettingsForm(ControlPanelForm):
	form_name = "Initialise Redis Settings"
	form_short_description = "Initialises and RESETS Redis settings to their default values."
	form_long_description = (
		"RESETS all Redis setting data and initialises Redis data stores. Do not use unless you know what you're doing."
	)
	form_allowed_ranks = [
		RankChoices.SUPERUSER,
	]
	
	def get_layout(self):
		return Layout()
	
	def submit(self, request):
		if self.is_valid():
			"""
			lich:settings
				- Nothing at the moment
			clock:settings
				- brightness (int)
				- colour (colour)
				- seconds_flashing (bool)
			"""
			settings_to_initialise = {
				"clock:settings": [
					(
						"brightness",
						"Clock Brightness",
						"The brightness of the clock, from 1-100",
						"int",
						"50",
					),
					(
						"colour",
						"Clock Colour",
						"The colour of the clock.",
						"colour",
						"rgb(255, 255, 0)",
					),
					(
						"seconds_flashing",
						"Seconds Indicator",
						"Whether the seconds indicator should flash or not.",
						"boolean",
						"1",
					)
				]
			}
			redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
			for settings_key, key_data in settings_to_initialise.items():
				types_key = f"{settings_key}:types"
				help_key = f"{settings_key}:help"
				display_key = f"{settings_key}:display"
				redis_connection.delete(settings_key, types_key, help_key, display_key)
				for key_name, key_display, key_help, key_type, key_value in key_data:
					# Set value in main hash
					redis_connection.hset(settings_key, key_name, key_value)
					# Set type
					redis_connection.hset(types_key, key_name, key_type)
					# Set help
					redis_connection.hset(help_key, key_name, key_help)
					# Set display
					redis_connection.hset(display_key, key_name, key_display)
			messages.success(request, f"Initialised {settings_to_initialise.keys()}")
	

FORM_CLASSES = {}
for form_class in (
	GatekeeperWebkeeperPurgeForm,
	ExpireMembershipsForm,
	MakeGatekeepersForm,
	MakeWebkeepersForm,
	AddRemoveRanksForm,
	CommitteeTransferForm,
	GetMembershipInfoForm,
	ClockSettingsForm,
	InitialiseRedisSettingsForm,
):
	FORM_CLASSES[slugify(form_class.form_name)] = form_class
