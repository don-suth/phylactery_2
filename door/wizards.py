from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.shortcuts import redirect
from formtools.wizard.views import SessionWizardView

from door.utils import is_cameron_hall_open, redis_check_cooldown, publish_letmein_request


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
		"confirm": is_cameron_hall_open
	}
	template_name = "door/letmein_wizard.html"
	
	def done(self, form_list, **kwargs):
		"""
		We'll get here when the form is submitted and valid.
		1) Check member cooldown
		2) If cooldown all good, publish the request
		3) Return to the door status page.
		"""
		cleaned_data = self.get_all_cleaned_data()
		member = self.request.unigames_member
		cooldown_check = redis_check_cooldown(member.pk)
		if cooldown_check:
			publish_letmein_request(member.short_name, cleaned_data["entrance"])
			messages.success(self.request, "Complete!")
			return redirect("door:status")
		else:
			messages.error(self.request, "Failed!")
			return redirect("door:status")
		