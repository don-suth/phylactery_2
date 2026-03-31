from functools import wraps
import redis
from django.conf import settings
from django.shortcuts import redirect


def redis_key_required(redis_key=""):
	"""
	Decorator for views - checks a given redis key.
	Allows access if a 1 is returned, and redirects otherwise.
	"""
	
	def decorator(view_func):
		
		def _view_wrap(request, *args, **kwargs):
			redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
			if str(redis_connection.get(redis_key)) == "1":
				return view_func(request, *args, **kwargs)
			else:
				return redirect("home")
		
		return wraps(view_func)(_view_wrap)
	
	return decorator
