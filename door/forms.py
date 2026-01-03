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
