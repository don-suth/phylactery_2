from django.urls import path

from .views import DoorView

app_name = "door"
urlpatterns = [
	path("", DoorView.as_view(), name="status"),
]