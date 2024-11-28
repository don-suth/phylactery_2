from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http.response import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView, DetailView, FormView
from .models import Member
from .decorators import gatekeeper_required
from .forms import ChangeEmailPreferencesForm


@method_decorator(gatekeeper_required, name="dispatch")
class MemberListView(ListView):
	model = Member
	paginate_by = 50
	template_name = "members/member_list.html"
	
	search_query = None
	
	def get_queryset(self):
		qs = Member.objects.all()
		
		self.search_query = self.request.GET.get("search")
		if self.search_query:
			qs = qs.filter(Q(short_name__icontains=self.search_query) | Q(long_name__icontains=self.search_query))
		
		return qs
	
	def get_context_data(self, *args, **kwargs):
		context = super().get_context_data(*args, **kwargs)
		context["search_query"] = self.search_query
		return context


@method_decorator(gatekeeper_required, name="dispatch")
class SignupHubView(TemplateView):
	template_name = "members/sign_up_hub.html"


@method_decorator(gatekeeper_required, name="dispatch")
class GatekeeperProfileView(DetailView):
	model = Member
	template_name = "members/gatekeeper_profile_view.html"


class MyProfileView(LoginRequiredMixin, DetailView):
	model = Member
	template_name = "members/my_profile_view.html"
	
	def get_object(self, queryset=None):
		member = self.request.unigames_member
		if member is None:
			raise Http404("Something went wrong. Please contact committee.")
		return member


class ChangeEmailPreferencesView(LoginRequiredMixin, FormView):
	form_class = ChangeEmailPreferencesForm
	template_name = "members/my_email_preferences.html"
	
	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		member = self.request.unigames_member
		if member is None:
			raise Http404("Something went wrong. Please contact committee.")
		kwargs.update(member=member)
		return kwargs

	def form_valid(self, form):
		form.submit()
		messages.success(self.request, "Email preferences saved.")
		return redirect("members:my_profile")