from django.urls import path

from .views import (
	HomePageView, AboutPageView, EventsPageView, RolePlayingPageView,
	CommitteeView, LifeMemberView, ContactView, ConstitutionView, WebcamsView, APIView, RegulationsView, MinutesView
)

urlpatterns = [
	path("", HomePageView.as_view(), name="home"),
	path("about/", AboutPageView.as_view(), name="about"),
	path("events/", EventsPageView.as_view(), name="events"),
	path("RPGs/", RolePlayingPageView.as_view(), name="rpgs"),
	path("committee/", CommitteeView.as_view(), name="committee"),
	path("lifemembers/", LifeMemberView.as_view(), name="life_members"),
	path("contact/", ContactView.as_view(), name="contact"),
	path("constitution/", ConstitutionView.as_view(), name="constitution"),
	path("api/", APIView.as_view(), name="api"),
	path("regulations/", RegulationsView.as_view(), name="regulations"),
	path("minutes/", MinutesView.as_view(), name="minutes"),
]
