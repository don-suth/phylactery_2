from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout


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


class LetMeInConfirmationForm(forms.Form):
	"""
	Displayed only if the system thinks Unigames is closed or Cameron Hall is already open.
	"""
	confirmation = forms.BooleanField(
		required=True,
		label="I confirm I have read the above"
	)


class LetMeInForm(forms.Form):
	entrance = forms.ChoiceField(
		choices={
			"tav": "Tav Side",
			"guild": "Guild Village Side"
		},
		label="Which side are you entering from",
		label_suffix="?",
		required=True,
	)
	confirmation = forms.BooleanField(
		required=True,
		label="I confirm that I have read the above"
	)
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_tag = False
		self.helper.layout = Layout(
			"entrance",
			"confirmation"
		)
