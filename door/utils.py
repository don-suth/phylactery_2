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


def redis_open_door():
	"""
	Updates Redis to open the Door.
	This involves:
		1) Changing the status of the "door:status" key.
		2) Publishing the status on the Pubsub channel "door:updates".
		3) Adding an entry to the Redis stream with:
			- timestamp
			- new status
			- member id
			- member name
			- source (phylactery/lich)
	# TODO: Change the redis keys to come from settings rather than being hardcoded.
	"""
	pass

def redis_close_door():
	"""
	Updates Redis to close the Door.
	This involves:
		1) Changing the status of the "door:status" key.
		2) Publishing the status on the Pubsub channel "door:updates".
		3) Adding an entry to the Redis stream with:
			- timestamp
			- new status
			- member id
			- member name
			- source (phylactery/lich)
	# TODO: Change the redis keys to come from settings rather than being hardcoded.
	"""
	pass
