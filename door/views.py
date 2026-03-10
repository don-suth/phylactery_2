from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, FormView

from members.decorators import gatekeeper_required
from door.forms import OpenCloseDoorForm, LetMeInForm
from door.utils import (
	get_door_status, redis_open_door, redis_close_door, is_cameron_hall_open, redis_check_cooldown,
	publish_letmein_request
)


class DoorStatusView(TemplateView):
	template_name = "door/door_status.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["door_status"], context["door_datetime"], context["door_display_name"] = get_door_status()
		return context


@method_decorator(gatekeeper_required, name="dispatch")
class OpenDoorFormView(FormView):
	form_class = OpenCloseDoorForm
	template_name = "door/open_door_form.html"
	
	def form_valid(self, form):
		member = self.request.unigames_member
		redis_open_door(member.pk, member.short_name)
		messages.success(self.request, "You have opened Unigames!")
		return redirect("door:status")


@method_decorator(gatekeeper_required, name="dispatch")
class CloseDoorFormView(FormView):
	form_class = OpenCloseDoorForm
	template_name = "door/close_door_form.html"
	
	def form_valid(self, form):
		member = self.request.unigames_member
		redis_close_door(member.pk, member.short_name)
		messages.success(self.request, "You have closed Unigames!")
		return redirect("door:status")


@method_decorator(login_required, name="dispatch")
class LetMeInView(FormView):
	form_class = LetMeInForm
	template_name = "door/letmein_form.html"
	
	def get_context_data(self, **kwargs):
		# Add the door status and whether Cameron Hall is (likely) locked to the context.
		context = super().get_context_data(**kwargs)
		context["door_status"], context["door_datetime"], context["door_display_name"] = get_door_status()
		context["cameron_hall_open"] = is_cameron_hall_open()
		return context
	
	def form_valid(self, form):
		member = self.request.unigames_member
		cooldown_check = redis_check_cooldown(member.pk)
		if cooldown_check:
			publish_letmein_request(member.short_name, form.cleaned_data["entrance"])
			messages.success(self.request, "Your message has been sent to the clubroom!")
			return redirect("door:status")
		else:
			messages.error(self.request, "You are currently on cooldown - please wait a little longer before trying again.")
			return redirect("door:status")
