from django.conf import settings
from allauth.socialaccount.models import SocialAccount
from door.models import DoorEvent, EventChoices
from members.models import Member
from celery import shared_task
from datetime import datetime, timezone as dt_timezone
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
			new_event_type = EventChoices.CLOSED
			dummy_event_type = EventChoices.OPENED
		else:
			new_event_type = EventChoices.OPENED
			dummy_event_type = EventChoices.CLOSED
		new_event_time = datetime.fromtimestamp(float(event_data), dt_timezone.utc)
		
		if most_recent_event is not None and most_recent_event.event_type == new_event_type:
			# This will occur when two "Door Opened" (or two "Door Closed") events happen consecutively.
			# The only reason this would occur is if someone forgot to change the door status upon arriving/leaving.
			# We maintain continuity by creating another dummy event, estimating the time which it would've occurred,
			# and then proceeding normally.
			
			# Assume the dummy event occurred halfway between this event and the previous
			dummy_event_time = most_recent_event.event_time + (new_event_time - most_recent_event.event_time) / 2
			dummy_event = DoorEvent.objects.create(
				event_time=dummy_event_time,
				event_type=dummy_event_type,
				previous_event=most_recent_event,
				member=None,
				notes={"dummy_event": True}
			)
			# Now we set the most recent event to be the dummy event we just created, and continue normally.
			most_recent_event = dummy_event
		
		# Try and evaluate the member that initiated the event.
		new_event_member = None
		try:
			if event_data["id_type"] == "member":
				new_event_member = Member.objects.get(pk=int(event_data["member_id"]))
			elif event_data["id_type"] == "discord":
				account = SocialAccount.objects.prefetch_related("user__member").get(uid=event_data["discord_id"])
				new_event_member = account.user.get_member
		except (Member.DoesNotExist, SocialAccount.DoesNotExist, SocialAccount.MultipleObjectsReturned):
			pass
		
		new_event = DoorEvent.objects.create(
			event_time=new_event_time,
			event_type=new_event_type,
			previous_event=most_recent_event,
			member=new_event_member,
			notes=event_data
		)
		
		# Add the ID to the list of IDs to delete
		events_to_delete.append(event_id)
		most_recent_event = new_event
		
	# Once we're done, delete the IDs.
	redis_connection.xdel("door:stream", *events_to_delete)
