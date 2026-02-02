from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from formtools.wizard.views import SessionWizardView


@method_decorator(login_required, name="dispatch")
class LetMeInWizard(SessionWizardView):
	"""
	This view handles the sending of "Let Me In" requests in a "wizard".
	The first form is skipped if Cameron Hall is closed and Unigames is open.
	Otherwise, the member is asked to confirm that they're really sure.
	"""
	
	# TODO: Implement cooldown
	
	form_list = [
		("confirm", None),
		("request", None),
	]
	condition_dict = {
		"confirm": True
	}
	template_name = "door/letmein_wizard.html"
	
	def done(self, form_list, **kwargs):
	
	