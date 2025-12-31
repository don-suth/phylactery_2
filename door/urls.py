from django.urls import path

from .views import DoorStatusView

app_name = "door"
urlpatterns = [
	path("", DoorStatusView.as_view(), name="status"),
]