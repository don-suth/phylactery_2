from django.urls import path
from members.autocompletes import MemberAutocomplete
from members.wizards import (
	FresherMembershipWizard,
	StaleMembershipWizard,
	LegacyMembershipWizard,
	FinanceRecordWizard
)
from members.views import (
	MemberListView,
	GatekeeperListView,
	SignupHubView,
	GatekeeperProfileView,
	MyProfileView,
	ChangeEmailPreferencesView,
	MakeSuperuserView,
	UnmakeSuperuserView,
)


app_name = "members"
urlpatterns = [
	path("signup/fresher/", FresherMembershipWizard.as_view(), name="signup_fresher"),
	path("signup/stale/<int:pk>/", StaleMembershipWizard.as_view(), name="signup_stale"),
	path("signup/legacy/", LegacyMembershipWizard.as_view(), name="signup_legacy"),
	path("signup/", SignupHubView.as_view(), name="signup_hub"),
	path("list/gatekeepers/", GatekeeperListView.as_view(), name="gatekeeper_list"),
	path("list/all/", MemberListView.as_view(), name="list"),
	path("profile/me/preferences/", ChangeEmailPreferencesView.as_view(), name="my_email_prefs"),
	path("profile/me/", MyProfileView.as_view(), name="my_profile"),
	path("profile/<int:pk>/", GatekeeperProfileView.as_view(), name="profile"),
	path("finance/", FinanceRecordWizard.as_view(), name="finance_record"),
	path("superuser/make/", MakeSuperuserView.as_view(), name="make_superuser"),
	path("superuser/unmake/", UnmakeSuperuserView.as_view(), name="unmake_superuser"),
	path("autocomplete_member", MemberAutocomplete.as_view(), name="autocomplete_member"),
]