from django.conf import settings
from django.utils import timezone
import datetime
import redis


def get_door_status():
	"""
	Gets and returns the following information from redis:
		- the current door status (either "OPEN" or "CLOSED")
		- when the door was last opened/closed (as a timezone aware datetime object)
		- who last opened/closed the door (string)
	"""
	redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
	# TODO: Change the redis key to come from settings rather than being hardcoded.
	door_status, door_timestamp, door_display_name = redis_connection.mget(
		["door:status", "door:timestamp", "door:display_name"]
	)
	door_datetime = datetime.datetime.fromtimestamp(float(door_timestamp), datetime.timezone.utc)
	return door_status, door_datetime, door_display_name


def redis_open_door(member_id, display_name):
	"""
	Updates Redis to open the Door.
	This involves:
		1) Changing the status of the following keys:
			- "door:status"
			- "door:timestamp"
			- "door:display_name"
		2) Publishing the status on the Pubsub channel "door:updates".
		3) Adding an entry to the Redis stream with:
			- timestamp
			- new status
			- member id
			- display name
			- source (phylactery/lich)
	# TODO: Change the redis keys to come from settings rather than being hardcoded.
	"""
	redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
	pipe = redis_connection.pipeline()
	timestamp = timezone.now().timestamp()
	pipe.set("door:status", "OPEN")
	pipe.set("door:timestamp", timestamp)
	pipe.set("door:display_name", display_name)
	pipe.xadd("door:stream", {
		"timestamp": timestamp,
		"new_status": "OPEN",
		"id_type": "member",
		"member_id": member_id,
		"display_name": display_name,
		"source": "phylactery"
	})
	pipe.publish("door:updates", "OPEN")
	pipe.execute()

def redis_close_door(member_id, display_name):
	"""
	Updates Redis to close the Door.
	This involves:
		1) Changing the status of the following keys:
			- "door:status"
			- "door:timestamp"
			- "door:display_name"
		2) Publishing the status on the Pubsub channel "door:updates".
		3) Adding an entry to the Redis stream with:
			- timestamp
			- new status
			- member id
			- display name
			- source (phylactery/lich)
	# TODO: Change the redis keys to come from settings rather than being hardcoded.
	"""
	redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
	pipe = redis_connection.pipeline()
	timestamp = timezone.now().timestamp()
	pipe.set("door:status", "CLOSED")
	pipe.set("door:timestamp", timestamp)
	pipe.set("door:display_name", display_name)
	pipe.xadd(
		"door:stream", {
			"timestamp": timestamp,
			"new_status": "CLOSED",
			"id_type": "member",
			"member_id": member_id,
			"display_name": display_name,
			"source": "phylactery"
		}
	)
	pipe.publish("door:updates", "CLOSED")
	pipe.execute()
	