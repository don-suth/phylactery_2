from django import forms

def HTML5DateInput():
	return forms.DateInput(
		attrs={
			"type": "date",
		},
		format="%Y-%m-%d"
	)