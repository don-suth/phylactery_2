from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML
from door.utils import get_door_status, is_cameron_hall_open


class OpenCloseDoorForm(forms.Form):
	confirmation = forms.BooleanField(
		required=True,
		label="I confirm I have read the above"
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.layout = Layout(
			"confirmation",
		)


class LetMeInForm(forms.Form):
	entrance = forms.ChoiceField(
		choices={
			"Tav": "Tav Side",
			"Guild": "Guild Village Side"
		},
		label="Which side are you entering from",
		label_suffix="?",
		required=True,
	)
	unigames_door_confirmation = forms.BooleanField(
		required=True,
		label="I confirm that I have read the above - I believe there is someone in the clubroom that can let me in",
		initial=True,
	)
	cameron_hall_door_confirmation = forms.BooleanField(
		required=True,
		label="I confirm that I have read the above - the Cameron Hall doors are closed",
		initial=True,
	)
	overall_confirmation = forms.BooleanField(
		required=True,
		label="I confirm that I have read and understand the above",
		initial=True
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.layout = Layout(
			Field("entrance"),
			Field("overall_confirmation"),
		)
		if is_cameron_hall_open():
			self.initial["cameron_hall_door_confirmation"] = False
			self.helper.layout.append(
				HTML("{% include 'door/snippets/hall_open_confirmation_snippet.html' %}")
			)
			self.helper.layout.append(
				Field("cameron_hall_door_confirmation")
			)
		else:
			self.helper.layout.append(
				Field("cameron_hall_door_confirmation", type="hidden")
			)
		
		clubroom_door_status, _, _ = get_door_status()
		if clubroom_door_status == "CLOSED":
			self.initial["unigames_door_confirmation"] = False
			self.helper.layout.append(
				HTML("{% include 'door/snippets/unigames_closed_confirmation_snippet.html' %}")
			)
			self.helper.layout.append(
				Field("unigames_door_confirmation")
			)
		else:
			self.helper.layout.append(
				Field("unigames_door_confirmation", type="hidden")
			)
