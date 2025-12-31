from django.db import models
from django.utils import timezone


class EventChoices(models.TextChoices):
	OPENED = "OPENED", "Door Opened"
	CLOSED = "CLOSED", "Door Closed"


class DoorEvent(models.Model):
	"""
	A model for logging Door Events.
	Each instance represents one event of the door either opening or closing.
	"""
	event_time = models.DateTimeField()
	event_type = models.CharField(
		max_length=6,
		choices=EventChoices.choices
	)
	previous_event = models.OneToOneField(
		"DoorEvent",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="next_event"
	)
	member = models.ForeignKey(
		"members.Member",
		on_delete=models.SET_NULL,
		null=True,
		blank=True
	)
	notes = models.JSONField(
		default=dict,
	)
	
	def __str__(self):
		return f"{timezone.localtime(self.event_time):%Y-%m-%d %H:%M:%S} - {self.event_type}"
