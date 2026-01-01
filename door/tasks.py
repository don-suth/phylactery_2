from django.conf import settings
from door.models import DoorEvent, EventChoices
from celery import shared_task
import redis


@shared_task(name="process_door_events")
def process_door_events():
	"""
	Scheduled task - once a day (or maybe once a week?)
	Consumes the stream entries from the door event stream,
	and converts them into database entries.
	"""
	redis_connection = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
	most_recent_event = DoorEvent.objects.last()
	events_to_delete = []
	stream_events = redis_connection.xrange("door:stream", "-", "+")
	for event_id, event_data in stream_events:
		if event_data["new_status"] == "CLOSED":
			event_type = EventChoices.CLOSED
		else:
			event_type = EventChoices.OPENED
		if most_recent_event is not None and most_recent_event.event_type != event_type:
			# Deploy corrective measures here.
			# Make another event, stick it in the halfway point between
			pass
		# Add in the new event
		# Add the ID to the list of IDs to delete
	# Once it's done, delete the IDs.

