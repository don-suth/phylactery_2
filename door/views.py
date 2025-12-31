from django.conf import settings
from django.views.generic import TemplateView
import redis


class DoorView(TemplateView):
	template_name = "pages/door.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
		door_status = redis_connection.get("door:status")
		context["door_status"] = door_status
		return context
