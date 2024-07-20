from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import UnigamesUser
from allauth.account import app_settings
from allauth.account.adapter import get_adapter
from allauth.account.utils import filter_users_by_email
from allauth.account.forms import AddEmailForm, UserForm
from allauth.account.models import EmailAddress
from allauth.socialaccount.forms import DisconnectForm
from allauth.socialaccount.models import SocialAccount
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder
from crispy_forms.bootstrap import StrictButton, FieldWithButtons


class UnigamesUserCreationForm(UserCreationForm):
	class Meta(UserCreationForm.Meta):
		model = UnigamesUser
		fields = ('email', 'username',)


class UnigamesUserChangeForm(UserChangeForm):
	class Meta:
		model = UnigamesUser
		fields = ('email', 'username',)


class SocialAccountModelChoiceField(forms.ModelChoiceField):
	def label_from_instance(self, obj):
		return f"{obj.get_provider_account().get_brand()['name']}: {obj.get_provider_account()}"


class UnigamesDisconnectForm(DisconnectForm):
	account = SocialAccountModelChoiceField(
		queryset=SocialAccount.objects.none(),
		widget=forms.RadioSelect,
		required=True,
		label="",
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.layout = Layout(
			"account",
		)
		

class UnigamesEmailChangeForm(AddEmailForm):
	display_verified_email_address = forms.EmailField(
		label="Current Email",
		required=False,
		disabled=True,
		widget=forms.TextInput(
			attrs={
				"type": "email"
			}
		)
	)
	
	display_pending_email_address = forms.EmailField(
		label="Current Email",
		required=False,
		disabled=True,
		widget=forms.TextInput(
			attrs={
				"type": "email"
			}
		),
		help_text="Your email address is still pending verification."
	)
	
	email = forms.EmailField(
		label="New Email Address",
		required=True,
		widget=forms.TextInput(
			attrs={
				"type": "email",
				"placeholder": "New Email Address"
			}
		),
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		pending_email_address = EmailAddress.objects.get_new(self.user)  # An email attached to the user, but not verified
		verified_email_address = EmailAddress.objects.get_verified(self.user)  # A currently verified email
		
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.layout = Layout()
		
		if verified_email_address:
			self.initial.update({"display_verified_email_address": verified_email_address.email})
			self.helper.layout.append(Field("display_verified_email_address"))
		if pending_email_address:
			self.initial.update({"display_pending_email_address": pending_email_address.email})
			self.helper.layout.append(Field("display_pending_email_address"))
			button_holder = ButtonHolder()
			button_holder.append(
				StrictButton(
					name="action_send",
					content="Resend Verification",
					input_type="submit",
					form="pending-email",
					css_class="btn-secondary btn-sm"
				)
			)
			if verified_email_address:
				self.fields["display_pending_email_address"].label = "Changing to"
				button_holder.append(
					StrictButton(
						name="action_remove",
						content="Cancel Change",
						input_type="submit",
						form="pending-email",
						css_class="btn-danger btn-sm"
					)
				)
			self.helper.layout.append(button_holder)
		self.helper.layout.append(Field("email"))
