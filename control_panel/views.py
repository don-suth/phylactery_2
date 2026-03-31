from django.core.exceptions import PermissionDenied
from django.utils.text import slugify
from django.shortcuts import reverse
from django.views.generic import TemplateView, FormView
from django.utils.decorators import method_decorator
from control_panel.forms import FORM_CLASSES
from members.decorators import gatekeeper_required


@method_decorator(gatekeeper_required, name="dispatch")
class ControlPanelListView(TemplateView):
	"""
	This view renders the list of control panel forms that
	the user has access to.
	"""
	template_name = "control_panel/control_panel_list.html"
	form_list = []
	
	def dispatch(self, request, *args, **kwargs):
		self.form_list = []
		for form_slug, form_class in FORM_CLASSES.items():
			if self.request.is_unigames_member and self.request.unigames_member.has_rank(
					*form_class.form_allowed_ranks
			):
				self.form_list.append(
					{
						"name": form_class.form_name,
						"description": form_class.form_short_description,
						"slug": form_slug
					}
				)
		if len(self.form_list) == 0:
			raise PermissionDenied
		return super().dispatch(request, *args, **kwargs)
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		context["form_list"] = self.form_list
		return context


@method_decorator(gatekeeper_required, name="dispatch")
class ControlPanelFormView(FormView):
	"""
	This view renders the requested form.
	"""
	template_name = "control_panel/control_panel_form.html"
	
	def get_form_class(self):
		return FORM_CLASSES.get(self.kwargs["slug"])
	
	def form_valid(self, form):
		form_response = form.submit(self.request)
		if form_response:
			return form_response
		else:
			return super().form_valid(form)
	
	def get_success_url(self):
		return reverse("control_panel:list")
	
	def dispatch(self, request, *args, **kwargs):
		form_class = self.get_form_class()
		if not self.request.is_unigames_member:
			raise PermissionDenied
		if not self.request.unigames_member.has_rank(*form_class.form_allowed_ranks):
			raise PermissionDenied
		return super().dispatch(request, *args, **kwargs)
