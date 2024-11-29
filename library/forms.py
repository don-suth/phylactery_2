from dal import autocomplete
from dal.forms import FutureModelForm
from datetime import date
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, HTML, Div, Field

from library.models import Item, Reservation, BorrowRecord, default_due_date
from library.controller import get_library_controller
from members.models import Member
from phylactery.form_fields import HTML5DateInput


class SelectLibraryItemsForm(forms.Form):
	"""
	Form to select library items, for the first step of the borrowing process.
	"""
	items = forms.ModelMultipleChoiceField(
		queryset=Item.objects.all(),
		widget=autocomplete.ModelSelect2Multiple(
			url="library:autocomplete_item",
			attrs={
				"data-theme": "bootstrap-5"
			}
		)
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.rejected_items = []
		self.different_due = False
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.include_media = False
		# noinspection PyTypeChecker
		self.helper.layout = Layout(
			Fieldset(
				"Borrow Items",
				HTML(
					"<p>Select items for the member to borrow. Member details will be filled out in the next step.</p>"
				),
				"items",
			)
		)
	
	def clean_items(self):
		"""
		Runs validation on the selected items,
		making sure that they can be borrowed before continuing.
		"""
		submitted_items = self.cleaned_data["items"]
		clean_items = []
		for item in submitted_items:
			item_info = item.get_availability_info()
			if not item_info["available_to_borrow"]:
				self.rejected_items.append(item.name)
			else:
				clean_items.append(item)
				if item_info["max_due_date"] != default_due_date():
					self.different_due = True
		if len(clean_items) == 0:
			raise ValidationError(
				"""None of the items you selected were available to borrow. If you think this is wrong, contact the Librarian.""",
				code="empty-items"
			)
		return clean_items


class ItemDueDateForm(forms.Form):
	"""
	Form to show and potentially change a due date when borrowing an item.
	One of these forms are displayed for each item selected in the preview step.
	"""
	item = forms.ModelChoiceField(
		widget=forms.HiddenInput,
		required=True,
		queryset=Item.objects.all(),
		disabled=True,
	)
	due_date = forms.DateField(
		required=True,
		widget=HTML5DateInput()
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		if self.initial["due_date"] != default_due_date():
			row_class = "table-warning"
		else:
			row_class = ""
		item_name = self.initial["item"].name
		item_img = self.initial["item"].image.url
		self.helper.layout = Layout(
			HTML(
				f"""
				<tr class="{row_class}">
					<td class="d-none d-md-table-cell">
						<img class="borrow-form-img" src="{item_img}">
					</td>
					<td class="align-middle" style="min-width: 60%;">
						{item_name}
					</td>
					<td style="max-width: 40%;">
				"""
			),
			"item",
			"due_date",
			HTML(
				"""
					</td>
				</tr>
				"""
			)
		)
	
	def clean(self):
		cleaned_data = super().clean()
		item = cleaned_data.get("item")
		due_date = cleaned_data.get("due_date")
		if item and due_date:
			# If both are valid so far:
			item_availability = item.get_availability_info()
			if not item_availability["available_to_borrow"]:
				raise ValidationError(f"{item} is not available to borrow at the moment.")
			if due_date > item_availability["max_due_date"]:
				self.add_error(
					field="due_date",
					error=f"The due date can't be set beyond the maximum due date for this item. "
					f"({item_availability['max_due_date']}"
				)
			if due_date < timezone.now().date():
				self.add_error(
					field="due_date",
					error="Due date cannot be in the past."
				)


class InternalBorrowerDetailsForm(forms.Form):
	member = forms.ModelChoiceField(
		queryset=Member.objects.all(),
		widget=autocomplete.ModelSelect2(
			url="members:autocomplete_member",
			attrs={
				"data-theme": "bootstrap-5"
			}
		)
	)
	address = forms.CharField(
		widget=forms.Textarea(
			attrs={
				"rows": 3
			}
		),
		required=True,
	)
	phone_number = forms.CharField(
		widget=forms.TextInput(
			attrs={
				"type": "tel"
			},
		),
		required=True,
		max_length=20,
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.include_media = False
		self.helper.layout = Layout(
			Fieldset(
				"Please enter the Borrowing Member's details below:",
				"member",
				"address",
				"phone_number",
			)
		)
	
	def clean_member(self):
		member = self.cleaned_data["member"]
		library_controller = get_library_controller()
		if not library_controller.member_has_borrowing_permissions(member):
			raise ValidationError("This member cannot borrow items.")
		return member


class InternalReservationRequestForm(forms.Form):
	name = forms.CharField(
		max_length=200,
		required=True,
		label="Your Name",
		disabled=True,
	)
	additional_details = forms.CharField(
		widget=forms.Textarea(
			attrs={
				"rows": 4
			}
		),
		required=True,
		label="Please enter additional details as to why you would like to reserve these items."
	)
	contact_email = forms.EmailField(
		required=True,
		label="Contact Email",
		disabled=True,
	)
	contact_phone = forms.CharField(
		max_length=20,
		required=True
	)
	requested_borrow_date = forms.DateField(
		required=True,
		widget=HTML5DateInput(),
		label="Requested borrow date"
	)
	requested_return_date = forms.DateField(
		required=True,
		widget=HTML5DateInput(),
		label="Requested return date"
	)
	items = forms.ModelMultipleChoiceField(
		queryset=Item.objects.all(),
		widget=autocomplete.ModelSelect2Multiple(
			url="library:autocomplete_item",
			attrs={
				"data-theme": "bootstrap-5"
			}
		),
		label="Requested items"
	)
	confirm = forms.BooleanField(
		required=True,
		initial=False,
		label="I agree to the above"
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.include_media = False
		# noinspection PyTypeChecker
		self.helper.layout = Layout(
			Fieldset(
				"Internal Reservation Request Form",
				HTML("{% include 'library/snippets/internal_reservation_disclaimer_1.html' %}"),
				Div(
					Div(
						"name",
						css_class="col-md"
					),
					Div(
						"contact_email",
						css_class="col-md"
					),
					css_class="row"
				),
				"additional_details",
				Div(
					Div(
						"contact_phone",
						css_class="col-md"
					),
					Div(
						"requested_borrow_date",
						css_class="col-md"
					),
					Div(
						"requested_return_date",
						css_class="col-md"
					),
					css_class="row"
				),
				"items",
				HTML("{% include 'library/snippets/internal_reservation_disclaimer_2.html' %}"),
				"confirm"
			)
		)
	
	def clean(self):
		# Performs additional validation on the form upon submission
		borrow_date = self.cleaned_data.get("requested_borrow_date")
		return_date = self.cleaned_data.get("requested_return_date")
		
		if borrow_date < date.today():
			self.add_error("requested_borrow_date", "Borrow date must be in the future")
		
		if return_date < date.today():
			self.add_error("requested_return_date", "Return date must be in the future")
		
		if return_date < borrow_date:
			# People can't return items before they've borrowed them.
			self.add_error("requested_return_date", "Return date cannot be before Borrow date")
	
	def done(self, member):
		"""
		Called by the view when the form is submitted and valid.
		Creates the relevant objects in the database.
		"""
		reservation_data = {
			"is_external": False,
			"internal_member": member,
			"requestor_name": self.cleaned_data["name"],
			"requestor_email": self.cleaned_data["contact_email"],
			"requestor_phone": self.cleaned_data["contact_phone"],
			"requested_date_to_borrow": self.cleaned_data["requested_borrow_date"],
			"requested_date_to_return": self.cleaned_data["requested_return_date"],
			"additional_details": self.cleaned_data["additional_details"],
			"librarian_comments": "",
			"borrower": None,
		}
		new_reservation = Reservation.objects.create(**reservation_data)
		new_reservation.reserved_items.set(self.cleaned_data["items"])


class ExternalReservationRequestForm(forms.Form):
	name = forms.CharField(
		max_length=200,
		required=True,
		label="Your Name"
	)
	organisation = forms.CharField(
		max_length=200,
		required=False,
		label="Your organisation name (optional)"
	)
	additional_details = forms.CharField(
		widget=forms.Textarea(
			attrs={
				"rows": 4
			}
		),
		required=True,
		label="Please enter additional details about your event and organisation (if applicable) here"
	)
	contact_email = forms.EmailField(
		required=True,
		label="Contact Email"
	)
	contact_phone = forms.CharField(
		max_length=20,
		required=True,
		label="Contact Phone"
	)
	requested_borrow_date = forms.DateField(
		required=True,
		widget=HTML5DateInput(),
		label="Requested borrow date"
	)
	requested_return_date = forms.DateField(
		required=True,
		widget=HTML5DateInput(),
		label="Requested return date"
	)
	items = forms.ModelMultipleChoiceField(
		queryset=Item.objects.all(),
		widget=autocomplete.ModelSelect2Multiple(
			url="library:autocomplete_item",
			attrs={
				"data-theme": "bootstrap-5"
			}
		),
		label="Requested items"
	)
	confirm = forms.BooleanField(
		required=True,
		initial=False,
		label="I agree to the above"
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.include_media = False
		# noinspection PyTypeChecker
		self.helper.layout = Layout(
			Fieldset(
				"External Reservation Request Form",
				HTML("{% include 'library/snippets/external_reservation_disclaimer_1.html' %}"),
				Div(
					Div(
						"name",
						css_class="col-md"
					),
					Div(
						"organisation",
						css_class="col-md"
					),
					css_class="row"
				),
				"additional_details",
				Div(
					Div(
						"contact_phone",
						css_class="col-md"
					),
					Div(
						"contact_email",
						css_class="col-md"
					),
					css_class="row"
				),
				Div(
					Div(
						"requested_borrow_date",
						css_class="col-md"
					),
					Div(
						"requested_return_date",
						css_class="col-md"
					),
					css_class="row"
				),
				"items",
				HTML("{% include 'library/snippets/external_reservation_disclaimer_2.html' %}"),
				"confirm"
			)
		)
	
	def clean(self):
		# Performs additional validation on the form upon submission
		borrow_date = self.cleaned_data.get("requested_borrow_date")
		return_date = self.cleaned_data.get("requested_return_date")
		
		if borrow_date < date.today():
			self.add_error("requested_borrow_date", "Borrow date must be in the future")
		
		if return_date < date.today():
			self.add_error("requested_return_date", "Return date must be in the future")
		
		if return_date < borrow_date:
			# People can't return items before they've borrowed them.
			self.add_error("requested_return_date", "Return date cannot be before Borrow date")
	
	def done(self):
		"""
		Called by the view when the form is submitted and valid.
		Creates the relevant objects in the database.
		"""
		reservation_data = {
			"is_external": True,
			"internal_member": None,
			"requestor_name": self.cleaned_data["name"],
			"requestor_email": self.cleaned_data["contact_email"],
			"requestor_phone": self.cleaned_data["contact_phone"],
			"requested_date_to_borrow": self.cleaned_data["requested_borrow_date"],
			"requested_date_to_return": self.cleaned_data["requested_return_date"],
			"additional_details": self.cleaned_data["additional_details"],
			"librarian_comments": "",
			"borrower": None,
		}
		if self.cleaned_data["organisation"]:
			reservation_data["additional_details"] = (
				f"Organisation: {self.cleaned_data['organisation']}\n-----\n{self.cleaned_data['additional_details']}"
			)
		new_reservation = Reservation.objects.create(**reservation_data)
		new_reservation.reserved_items.set(self.cleaned_data["items"])


class ReservationModelForm(FutureModelForm):
	class Meta:
		model = Reservation
		fields = [
			"is_external", "internal_member",
			"requestor_name", "requestor_email", "requestor_phone",
			"reserved_items",
			"requested_date_to_borrow", "requested_date_to_return",
			"additional_details", "approval_status",
			"librarian_comments"
		]
		disabled_fields = [
			"is_external", "internal_member",
			"requestor_name", "requestor_email", "requestor_phone",
			"additional_details",
		]
		widgets = {
			"is_external": forms.TextInput(),
			"reserved_items": autocomplete.ModelSelect2Multiple(
				url="library:autocomplete_item",
				attrs={
					"data-theme": "bootstrap-5"
				}
			),
			"requested_date_to_borrow": HTML5DateInput(),
			"requested_date_to_return": HTML5DateInput(),
			"additional_details": forms.Textarea(
				attrs={
					"rows": 4,
				}
			),
			"librarian_comments": forms.Textarea(
				attrs={
					"rows": 4,
				}
			)
		}
		labels = {
			"reserved_items": "Requested items"
		}
	
	def __init__(self, *args, **kwargs):
		view_only = kwargs.pop("view_only", False)
		super().__init__(*args, **kwargs)
		if view_only:
			self.Meta.disabled_fields = self.Meta.fields
		for field_name in self.Meta.disabled_fields:
			self.fields.get(field_name).disabled = True
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.include_media = False
		# noinspection PyTypeChecker
		self.helper.layout = Layout(
			Fieldset(
				"Reservation",
				Div(
					Div(css_class="col-md"),
					Div("is_external", css_class="col-md"),
					css_class="row",
				),
				"requestor_email", "requestor_phone",
				"reserved_items",
				HTML("{% include 'library/snippets/problem_items_snippet.html' %}"),
				Div(
					Div("requested_date_to_borrow", css_class="col-md"),
					Div("requested_date_to_return", css_class="col-md"),
					css_class="row",
				),
				"additional_details", "approval_status",
				"librarian_comments",
				HTML("{% include 'library/snippets/librarian_comment_warning.html' %}"),
			)
		)
		if self.initial.get("is_external"):
			self.helper.layout[0][0][0].append("requestor_name")
			self.helper.layout[0][0][1].css_class = "col-md border border-danger bg-danger-subtle"
		else:
			self.helper.layout[0][0][0].append("internal_member")


class ReturnItemForm(forms.Form):
	"""
	Form for selecting items for returning (and also putting in comments.)
	One of these forms are displayed for each item selected in the preview step.
	"""
	borrow_record = forms.ModelChoiceField(
		widget=forms.HiddenInput,
		required=True,
		queryset=BorrowRecord.objects.all(),
	)
	returned = forms.BooleanField(
		required=False
	)
	comments = forms.CharField(
		required=False,
		widget=forms.Textarea(
			attrs={
				"rows": 4,
				"placeholder": "Comments"
			}
		),
		label="",
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		item_name = self.initial["borrow_record"].item.name
		item_img = self.initial["borrow_record"].item.image.url
		self.helper.layout = Layout(
			HTML(
				f"""
					<tr>
						</td>
						<td class="d-none d-md-table-cell">
							<img class="borrow-form-img" src="{item_img}">
						</td>
						<td class="align-middle" style="max-width: 30%;">
							{item_name}
				"""
			),
			Field("returned", wrapper_class="mt-3"),
			HTML(
				"""
						</td>
						<td style="min-width: 70%;">
					"""
			),
			"borrow_record",
			"comments",
			HTML(
				"""
					</td>
					<td>
				"""
			),
			HTML(
				"""
					</td>
				</tr>
				"""
			)
		)


ReturnItemFormset = forms.formset_factory(ReturnItemForm, extra=0)


class VerifyReturnForm(forms.Form):
	"""
	A form for the Librarian, to verify items as returned
	"""
	borrow_record = forms.ModelChoiceField(
		widget=forms.HiddenInput,
		required=True,
		queryset=BorrowRecord.objects.all(),
	)
	verified = forms.BooleanField(
		required=False
	)
	comments = forms.CharField(
		required=False,
		widget=forms.Textarea(
			attrs={
				"rows": "3",
				"placeholder": "Comments"
			}
		),
		label="",
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		
		self.helper.layout = Layout(
			Div(
				Div(
					Div(
						HTML(
							"""<img class="borrow-form-img" src="{{ sub_form.initial.borrow_record.item.image.url }}">"""
						),
						css_class="col-md-2 mb-1",
					),
					Div(
						HTML(
							"""
								<strong>Item Name</strong>: {{ sub_form.initial.borrow_record.item.name }}<br />
								<strong>Borrower</strong>: {{ sub_form.initial.borrow_record.borrower.borrower_name }}<br />
								<strong>Borrowed</strong>: {{ sub_form.initial.borrow_record.borrowed_datetime }}<br />
								"""
						),
						css_class="col-md mb-1",
					),
					Div(
						HTML(
							"""
						<strong>Due Date</strong>: {{ sub_form.initial.borrow_record.due_date }}<br />
						<strong>Returned</strong>: {{ sub_form.initial.borrow_record.returned_datetime }}<br />
						<strong>Returning Gatekeeper</strong>: {{ sub_form.initial.borrow_record.return_authorised_by }}
						"""
						),
						css_class="col-md mb-1",
					),
					Div(
						"borrow_record",
						"comments",
						"verified",
						css_class="col-md mb-1",
					),
					css_class="row"
				),
				css_class="card-body"
			)
		)


VerifyReturnFormset = forms.formset_factory(VerifyReturnForm, extra=0)


class ExternalBorrowerDetailsForm(forms.Form):
	"""
	Form to collect details from an external borrower.
	"""
	borrower_name = forms.CharField(
		required=True,
		label="Borrower name"
	)
	address = forms.CharField(
		widget=forms.Textarea(
			attrs={
				"rows": 3
			}
		),
		required=True,
		label="Borrower address"
	)
	phone_number = forms.CharField(
		widget=forms.TextInput(
			attrs={
				"type": "tel"
			},
		),
		required=True,
		max_length=20,
		label="Borrower phone number"
	)
	confirm = forms.BooleanField(
		required=True,
		initial=False,
		label="I agree to the above"
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.include_media = False
		
		self.helper.layout = Layout(
			Fieldset(
				"Borrower Details",
				"borrower_name",
				"address",
				"phone_number",
				HTML("{% include 'library/snippets/external_reservation_borrow_disclaimer.html' %}"),
				"confirm",
			)
		)
	


class ReservationSelectItemForm(forms.Form):
	"""
	Form to show and select which items in the Reservation will actually be borrowed.
	"""
	item = forms.ModelChoiceField(
		widget=forms.HiddenInput,
		required=True,
		queryset=Item.objects.all(),
		disabled=True,
	)
	due_date = forms.DateField(
		widget=HTML5DateInput(),
		required=True,
		disabled=True,
	)
	selected = forms.BooleanField(
		required=False,
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.layout = Layout(
			HTML(
				"""
				<tr>
					<td class="d-none d-md-table-cell">
						<img class="borrow-form-img" src="{{ sub_form.initial.item.image.url }}">
					</td>
					<td>
						{{ sub_form.initial.item.name }}
					</td>
					<td>
				"""
			),
			"item",
			"due_date",
			HTML(
				"""
					</td>
					<td>
				"""
			),
			"selected",
			HTML(
				"""
					</td>
				</tr>
				"""
			),
		)

