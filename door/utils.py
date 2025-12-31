from django.conf import settings
import redis


def get_door_status():
	"""
	Returns the status of the Door from Redis.
	"""
	redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
	# TODO: Change the redis key to come from settings rather than being hardcoded.
	door_status = redis_connection.get("door:status")
	return door_status

