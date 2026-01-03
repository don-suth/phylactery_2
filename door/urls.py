from django.urls import path

from .views import DoorStatusView, OpenDoorFormView, CloseDoorFormView

app_name = "door"
urlpatterns = [
	path("", DoorStatusView.as_view(), name="status"),
	path("open/", OpenDoorFormView.as_view(), name="open"),
	path("close/", CloseDoorFormView.as_view(), name="close"),
]