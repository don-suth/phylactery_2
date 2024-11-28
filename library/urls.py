from django.urls import path
from library.autocompletes import ItemAutocomplete, LibraryTagAutocomplete
from library.wizards import (
	InternalBorrowItemsWizard,
	InternalReservationBorrowItemsWizard,
	ExternalReservationBorrowItemsWizard,
)
from library.views import (
	ItemDetailView,
	ItemListView,
	ItemSearchView,
	TagListView,
	TagDetailView,
	DashboardView,
	ExternalReservationRequestView,
	InternalReservationRequestView,
	ReservationApprovalView,
	VerifyReturnsView,
	ReturnItemsView,
	LibraryHomeView,
	ReservationBorrowRedirectView,
	SearchSyntaxView,
)


app_name = 'library'
urlpatterns = [
	path("dashboard/", DashboardView.as_view(), name="dashboard"),
	path("request/external/", ExternalReservationRequestView.as_view(), name="reservation_external"),
	path("request/internal/", InternalReservationRequestView.as_view(), name="reservation_internal"),
	path("approve/<int:pk>/", ReservationApprovalView.as_view(), name="approve_reservation"),
	path("verify/", VerifyReturnsView.as_view(), name="verify_returns"),
	path("item/<slug:slug>/", ItemDetailView.as_view(), name="item_detail"),
	path("tag/<slug:slug>/", TagDetailView.as_view(), name="tag_detail"),
	path("items/", ItemListView.as_view(), name="item_list"),
	path("tags/", TagListView.as_view(), name="tag_list"),
	path("borrow/", InternalBorrowItemsWizard.as_view(), name="borrow_wizard"),
	path("borrow/reservation/<int:pk>/", ReservationBorrowRedirectView.as_view(), name="borrow_reservation"),
	path("borrow/reservation/internal/<int:pk>/", InternalReservationBorrowItemsWizard.as_view(), name="borrow_internal_reservation"),
	path("borrow/reservation/external/<int:pk>/", ExternalReservationBorrowItemsWizard.as_view(), name="borrow_external_reservation"),
	path("return/<int:pk>/", ReturnItemsView.as_view(), name="return"),
	path("search", ItemSearchView.as_view(), name="search"),
	path("syntax/", SearchSyntaxView.as_view(), name="syntax"),
	path("autocomplete_item", ItemAutocomplete.as_view(), name="autocomplete_item"),
	path("autocomplete_tag", LibraryTagAutocomplete.as_view(), name="autocomplete_tag"),
	path("", LibraryHomeView.as_view(), name="home"),
]