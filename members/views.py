from django.db.models import Q
from django.views.generic import ListView
from .models import Member


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
