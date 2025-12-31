from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, FormView

from members.decorators import gatekeeper_required
from door.forms import OpenCloseDoorForm
from door.utils import get_door_status


class DoorStatusView(TemplateView):
	template_name = "door/door_status.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["door_status"] = get_door_status()
		return context


@method_decorator(gatekeeper_required, name="dispatch")
class OpenDoorFormView(FormView):
	form_class = OpenCloseDoorForm
	template_name = "door/open_door_form.html"


@method_decorator(gatekeeper_required, name="dispatch")
class CloseDoorFormView(FormView):
	form_class = OpenCloseDoorForm
	template_name = "door/close_door_form.html"
