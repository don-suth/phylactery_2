from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import Now
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, TemplateView, FormView, UpdateView
from django.utils import timezone
from django.utils.decorators import method_decorator
from datetime import timedelta
from library.models import Item, LibraryTag, BorrowerDetails, Reservation, ReservationStatus, BorrowRecord
from library.forms import ExternalReservationRequestForm, InternalReservationRequestForm, ReservationModelForm, ReturnItemFormset, VerifyReturnFormset
from library.search import SearchQueryManager
from members.decorators import gatekeeper_required, committee_required


@method_decorator(gatekeeper_required, name="dispatch")
class DashboardView(TemplateView):
	template_name = "library/dashboard_view.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		today = timezone.now().date()
		context["unapproved_reservations"] = Reservation.objects.filter(
			approval_status=ReservationStatus.PENDING
		)
		context["upcoming_reservations"] = Reservation.objects.filter(
			requested_date_to_borrow__gte=today, is_active=True
		)
		context["reservations_today"] = Reservation.objects.filter(
			requested_date_to_borrow=today, is_active=True
		)
		context["to_be_verified"] = BorrowRecord.objects.filter(
			returned=True, verified_returned=False
		)
		context["outstanding_borrowers"] = BorrowerDetails.objects.filter(
			completed=False
		).annotate(
			outstanding_count=Count(
				"borrow_records",
				filter=Q(
					borrow_records__borrowed_datetime__lte=Now(),
					borrow_records__returned_datetime=None
				),
			)
		).annotate(
			overdue_count=Count(
				"borrow_records",
				filter=Q(
					borrow_records__borrowed_datetime__lte=Now(),
					borrow_records__returned_datetime=None,
					borrow_records__due_date__lt=today,
				),
			)
		)
		context["currently_borrowed"] = Item.objects.filter(
			borrow_records__borrowed_datetime__lte=Now(),
			borrow_records__returned_datetime=None
		)
		context["overdue_items"] = Item.objects.filter(
			borrow_records__borrowed_datetime__lte=Now(),
			borrow_records__returned_datetime=None,
			borrow_records__due_date__lt=today,
		)
		return context


class ItemDetailView(DetailView):
	model = Item
	template_name = "library/item_detail_view.html"
	slug_field = "slug"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["item_info"] = self.object.get_availability_info()
		if context["item_info"]["in_clubroom"] is False:
			today = timezone.now().date()
			tomorrow = today + timedelta(days=1)
			if context["item_info"]["expected_available_date"] not in [today, tomorrow]:
				context["available_str"] = ""
			elif context["item_info"]["expected_available_date"] == today:
				context["available_str"] = "today"
			elif context["item_info"]["expected_available_date"] == tomorrow:
				context["available_str"] = "tomorrow"
		context["item_types"] = self.object.base_tags.filter(is_item_type=True)
		return context


class ItemListView(ListView):
	model = Item
	template_name = "library/item_list_view.html"
	context_object_name = "items_list"
	paginate_by = 24


class ItemSearchView(ListView):
	"""
	Identical to the ItemListView above,
	except we also handle simple searches.
	"""
	model = Item
	template_name = "library/item_search_view.html"
	context_object_name = "items_list"
	paginate_by = 24
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.query = None
		self.manager = None
	
	def setup(self, request, *args, **kwargs):
		super().setup(request, *args, **kwargs)
		self.query = self.request.GET.get("q", "")
		if self.query:
			self.manager = SearchQueryManager(query=self.query)
			self.manager.evaluate()
	
	def get_queryset(self):
		if self.manager:
			return self.manager.get_results()
		else:
			return Item.objects.none()
	
	def get_context_data(self, *args, **kwargs):
		context = super().get_context_data(*args, **kwargs)
		if self.manager:
			context["search_warnings"] = self.manager.warnings
			context["search_errors"] = self.manager.errors
		if self.query:
			context["query"] = self.query
		return context


class SearchSyntaxView(TemplateView):
	template_name = "library/search_syntax.html"


class TagListView(ListView):
	model = LibraryTag
	template_name = "library/tag_list_view.html"
	context_object_name = "tags_list"
	
	def get_queryset(self):
		qs = (
			LibraryTag.objects.exclude(name__startswith="Item: ")
			.annotate(num_items=Count('computed_items'))
			.filter(num_items__gt=0, is_item_type=False, is_tag_category=False)
			.order_by('-num_items', 'name')
		)
		return qs


class TagDetailView(ListView):
	model = Item
	template_name = "library/item_list_view.html"
	context_object_name = "items_list"
	
	def get_queryset(self):
		self.tag = get_object_or_404(LibraryTag, slug=self.kwargs["slug"])
		qs = (
			Item.objects.filter(
				Q(base_tags__in=[self.tag]) | Q(computed_tags__in=[self.tag])
			).distinct()
		)
		return qs

	def get_context_data(self, *args, **kwargs):
		context = super().get_context_data(*args, **kwargs)
		context["page_title"] = f"All items tagged with '{self.tag}'"
		context["parent_tags"] = self.tag.parents.exclude(name__startswith="Item: ")
		context["child_tags"] = self.tag.children.exclude(name__startswith="Item: ")
		return context


class ExternalReservationRequestView(FormView):
	"""
	Renders the External Reservation Request form.
	"""
	form_class = ExternalReservationRequestForm
	template_name = "library/reservation_form.html"
	
	def form_valid(self, form):
		"""
		When the form is submitted and is valid:
			1. Create the relevant objects in the database.
			2. TODO: Send notification to the librarian.
			3. TODO: Send email receipt to the submitter.
			4. Redirect to the Library Home page with a success message.
		"""
		form.done()
		messages.success(self.request, "Your form was successfully submitted! We will get in touch soon.")
		return redirect("home")


class InternalReservationRequestView(LoginRequiredMixin, FormView):
	"""
	Renders the Internal Reservation Request form.
	"""
	form_class = InternalReservationRequestForm
	template_name = "library/reservation_form.html"
	
	def get_initial(self):
		initial = super().get_initial()
		self.submitting_member = self.request.user.get_member
		if self.submitting_member is None:
			raise PermissionDenied
		initial["name"] = self.submitting_member.long_name
		initial["contact_email"] = self.submitting_member.user.email
		return initial
	
	def form_valid(self, form):
		"""
		When the form is submitted and is valid:
			1. Create the relevant objects in the database.
			2. TODO: Send notification to the librarian.
			3. TODO: Send email receipt to the submitter.
			4. Redirect to the Library Home page with a success message.
		"""
		form.done(member=self.submitting_member)
		messages.success(self.request, "Your form was successfully submitted! We will get in touch soon.")
		return redirect("home")


@method_decorator(gatekeeper_required, name="dispatch")
class ReservationApprovalView(UpdateView):
	"""
	For the Librarian - renders the form for approving Reservations
	"""
	model = Reservation
	form_class = ReservationModelForm
	template_name = "library/reservation_form.html"
	
	def get_context_data(self, **kwargs):
		"""
		We check the requested items. If any of them might not be back in time,
		then we show an alert.
		"""
		context = super().get_context_data(**kwargs)
		if self.object.approval_status == ReservationStatus.PENDING:
			# Don't show the warnings if the form is already approved.
			maybe_not_available = []
			normally_not_borrowable = []
			for item in self.object.reserved_items.all():
				if not item.is_borrowable:
					normally_not_borrowable.append(item.name)
				expected_available_date = item.get_availability_info()["expected_available_date"]
				if expected_available_date is not None and expected_available_date > self.object.requested_date_to_borrow:
					maybe_not_available.append((item.name, expected_available_date))
			context["maybe_not_available"] = maybe_not_available
			context["normally_not_borrowable"] = normally_not_borrowable
		context["view_only"] = not self.request.user.member.is_committee()
		return context
	
	def get_form_kwargs(self):
		# If the viewer of the form is not Committee,
		# then don't let them change anything.
		kwargs = super().get_form_kwargs()
		if not self.request.user.member.is_committee():
			kwargs.update({"view_only": True})
		return kwargs
	
	def form_valid(self, form):
		"""
		A couple of things to do here:
			0. Gatekeepers are able to view. Make sure they can't change.
			1. If the status is updated, update the status_updated timestamp
			2. If the status is now approved, set is_active to True
			3. If changes have been made, email the requestor.
				- Track changes in:
					- approval_status, reserved_items, librarian_comments
					- requested_date_to_borrow, requested_date_to_return,
		"""
		if form.has_changed() and self.request.user.member.is_committee():
			if "approval_status" in form.changed_data:
				form.instance.status_update_datetime = timezone.now()
				if form.cleaned_data["approval_status"] == ReservationStatus.APPROVED:
					form.instance.is_active = True
			track_field_changes = {
				"approval_status", "reserved_items", "librarian_comments",
				"requested_date_to_borrow",	"requested_date_to_return"
			}
			if len(track_field_changes & set(form.changed_data)) >= 1:
				# Any of the fields that we care about have been updated.
				# TODO: Send an email to the requestor with the updated changes.
				pass
			form.save()
			messages.success(self.request, "Reservation updated.")
		return redirect("library:dashboard")


@method_decorator(gatekeeper_required, name="dispatch")
class ReturnItemsView(FormView):
	"""
	Renders a form that allows returning of items.
	Each form loads a single BorrowerDetails object.
	If a Member has borrowed several items separately,
	this form will have to be used more than once to return them all.
	"""
	form_class = ReturnItemFormset
	template_name = "library/return_items_view.html"
	
	def get_initial(self):
		pk = self.kwargs.get("pk", None)
		self.borrower_details = get_object_or_404(BorrowerDetails, pk=pk)
		if self.borrower_details in BorrowerDetails.objects.filter(completed=True):
			raise Http404
		initial = []
		for borrow_record in self.borrower_details.borrow_records.filter(
			borrowed_datetime__lte=Now(),
			returned_datetime=None,
		):
			initial.append({
				"borrow_record": borrow_record
			})
		return initial
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		context["borrower_name"] = self.borrower_details.borrower_name
		return context
	
	def form_valid(self, form):
		"""
		Check for any forms that have the returned box checked, and process them.
		"""
		returned = 0
		for sub_form in form.forms:
			sub_form_data = sub_form.cleaned_data
			if sub_form_data["returned"] is True:
				borrow_record = sub_form_data["borrow_record"]
				borrow_record.returned_datetime = timezone.now()
				borrow_record.comments = sub_form_data["comments"]
				borrow_record.return_authorised_by = self.request.user.member.long_name
				borrow_record.save()
				returned += 1
		if returned > 0:
			messages.success(self.request, f"Successfully returned {returned} items.")
			# TODO: Send email receipt to borrower that items have been returned.
			# TODO: Send notification to the Librarian that items have been returned.
			if self.borrower_details in BorrowerDetails.objects.filter(completed=True):
				for reservation in Reservation.objects.filter(borrower=self.borrower_details):
					# This borrow record is now completed. We can update the reservation to be completed as well.
					reservation.set_completed()
		return redirect("library:dashboard")
		

@method_decorator(committee_required, name="dispatch")
class VerifyReturnsView(FormView):
	"""
	For the Librarian - renders the form for verifying returned items.
	"""
	form_class = VerifyReturnFormset
	template_name = "library/verify_returns_view.html"
	
	def get_initial(self):
		initial = []
		for borrow_record in BorrowRecord.objects.filter(
				borrowed_datetime__lte=Now(),
				returned_datetime__lte=Now(),
				verified_returned=False
		):
			initial.append(
				{
					"borrow_record": borrow_record,
					"comments": borrow_record.comments
				}
			)
		return initial
	
	def form_valid(self, form):
		verified = 0
		for sub_form in form.forms:
			sub_form_data = sub_form.cleaned_data
			if sub_form_data["verified"] is True:
				borrow_record = sub_form_data["borrow_record"]
				borrow_record.verified_returned = True
				borrow_record.comments = sub_form_data["comments"]
				borrow_record.save()
				verified += 1
		if verified > 0:
			messages.success(self.request, f"Successfully verified {verified} items.")
		return redirect("library:dashboard")


class LibraryHomeView(TemplateView):
	"""
	Renders the Home page for the library.
	Different from the Dashboard view.
	"""
	
	template_name = "library/library_home.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["book_count"] = Item.objects.filter(base_tags__name__in=["Item Type: Book"]).count()
		context["board_game_count"] = Item.objects.filter(base_tags__name__in=["Item Type: Board Game"]).count()
		context["card_game_count"] = Item.objects.filter(base_tags__name__in=["Item Type: Card Game"]).count()
		context["other_count"] = Item.objects.filter(base_tags__name__in=["Item Type: Other"]).count()
		return context

@method_decorator(gatekeeper_required, name="dispatch")
class ReservationBorrowRedirectView(DetailView):
	"""
	This view simply performs a redirect to the correct Wizard.
	"""
	
	model = Reservation
	
	def dispatch(self, request, *args, **kwargs):
		reservation = self.get_object()
		if reservation.is_external:
			return redirect("library:borrow_external_reservation", pk=reservation.pk)
		else:
			return redirect("library:borrow_internal_reservation", pk=reservation.pk)
