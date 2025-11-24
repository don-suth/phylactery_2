from members.models import Rank
from django.conf import settings
from django.views.generic import TemplateView, RedirectView
from django.utils import timezone
from blog.models import BlogPost
from library.models import Item
import redis


class HomePageView(TemplateView):
	template_name = "pages/home.html"
	featured_tag_slug = "featured"
	featured_item_limit = 5
	recent_blog_post_limit = 3
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		
		context["featured_items"] = Item.objects.filter(
			base_tags__slug__in=[self.featured_tag_slug]
		).distinct().order_by("name")
		
		context["recent_blogposts"] = BlogPost.objects.filter(
			publish_on__lte=timezone.now()
		).distinct().order_by("-publish_on")[:self.recent_blog_post_limit]
		
		return context


class AboutPageView(TemplateView):
	template_name = "pages/about.html"


class EventsPageView(TemplateView):
	template_name = "pages/events.html"


class RolePlayingPageView(TemplateView):
	template_name = "pages/role_playing.html"


class LifeMemberView(TemplateView):
	template_name = "pages/life_members.html"
	

class ContactView(TemplateView):
	template_name = "pages/contact.html"


class ConstitutionView(TemplateView):
	template_name = "pages/constitution.html"

	
class WebcamsView(TemplateView):
	# Deprecated. URL will now redirect to DoorView.
	template_name = "pages/webcams.html"


class APIView(TemplateView):
	template_name = "coming_soon.html"

	
class RegulationsView(TemplateView):
	template_name = "pages/regulations.html"


class MinutesView(TemplateView):
	template_name = "pages/minutes.html"


class CommitteeView(TemplateView):
	template_name = "pages/committee.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["committee"] = Rank.objects.get_committee()
		return context


class DoorView(TemplateView):
	template_name = "pages/door.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
		door_status = redis_connection.get("door:status")
		context["door_status"] = door_status
		return context
