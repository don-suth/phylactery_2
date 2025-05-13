import datetime
from django.contrib.auth.models import Permission
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Case, When, Value, Q
from django.db.models.functions import Now
from django.utils import timezone

from accounts.models import UnigamesUser
from library.models import BorrowRecord
from members.codes import generate_reference_code

# Advanced models are models we shouldn't let anyone but Webkeepers touch.
# For permission syncing.
ADVANCED_MODELS = [
	"logentry", "permission", "group", "contenttype", "session", "site",
	"emailaddress", "emailconfirmation", "socialaccount", "socialapp", "socialtoken",
	"unigamesuser"
]


class Member(models.Model):
	"""
	Stores all information about a single Unigames member.
	"""
	
	# Rather than a first name and last name, we track a short name and long name.
	# This is for too many reasons to list here. But it is intentional.
	short_name = models.CharField(max_length=100)
	long_name = models.CharField(max_length=200)
	
	# Members provide their own pronouns. The membership form provides common options, but members can type their own.
	pronouns = models.CharField(max_length=50)
	
	student_number = models.CharField(max_length=10, blank=True)
	join_date = models.DateField()
	
	# Unigames Committee can use this field to store notes on a particular member.
	notes = models.TextField(blank=True)
	
	# Members can create user accounts linked to their member information.
	user = models.OneToOneField(UnigamesUser, blank=True, null=True, on_delete=models.SET_NULL, related_name="member")
	
	# A simple checkbox that controls globally whether the member is sent optional emails.
	# (they will still receive transactional emails and reminder emails, regardless)
	optional_emails = models.BooleanField(default=True)
	
	class Meta:
		ordering = ["long_name"]
	
	# Methods
	def __str__(self):
		return self.long_name
	
	def is_fresher(self):
		# Simple test - if they joined this year, they are a fresher.
		if self.join_date.year == timezone.now().year:
			return True
		else:
			return False
	
	@property
	def email(self):
		try:
			return self.user.email
		except ObjectDoesNotExist:
			return None
		
	def add_rank(self, rank_name):
		"""
		Adds the chosen rank to this member.
		"""
		Rank.objects.create(
			member=self,
			rank_name=rank_name
		)
	
	def has_rank(self, *rank_names):
		# Returns True if the member has a non-expired rank with any of the given types.
		# Returns False otherwise.
		return self.ranks.filter(expired=False, rank_name__in=rank_names).exists()
	
	def remove_rank(self, rank_name):
		"""
		Expires all active ranks of the chosen type from this member.
		"""
		ranks_to_expire = self.ranks.filter(expired=False, rank_name=rank_name)
		for rank in ranks_to_expire:
			rank.set_expired()
	
	def has_active_membership(self):
		# Returns True if the member has a valid membership.
		return self.memberships.filter(expired=False).exists()
	
	def is_valid_member(self):
		# Returns True if the member has a valid membership (or is a life member) and does not have the excluded rank.
		return (
			(self.has_active_membership() or self.has_rank(RankChoices.LIFEMEMBER))
			and not self.has_rank(RankChoices.EXCLUDED)
		)
	
	def get_most_recent_membership(self):
		# Returns the most recent Membership object of this user, or None if they have none.
		return self.memberships.order_by("-date_purchased").first()
	
	def has_purchased_membership_this_year(self):
		# Returns True if the most recent membership for this member was purchased this year.
		membership = self.get_most_recent_membership()
		if membership is not None and membership.date_purchased.year == timezone.now().year:
			return True
		else:
			return False
	
	def is_life_member(self):
		# Convenience alias function.
		return self.has_rank(RankChoices.LIFEMEMBER)
	
	# The following are the preferred methods of testing for privileges.
	# Webkeepers get these privileges as well for debugging.
	def is_gatekeeper(self):
		return self.is_valid_member() and self.has_rank(RankChoices.GATEKEEPER, RankChoices.WEBKEEPER)
	
	def is_committee(self):
		return self.is_valid_member() and self.has_rank(RankChoices.COMMITTEE, RankChoices.WEBKEEPER)
	
	def is_webkeeper(self):
		return self.is_valid_member() and self.has_rank(RankChoices.WEBKEEPER)
	
	def is_exec(self):
		return (
			self.is_valid_member() and
			self.has_rank(
				RankChoices.PRESIDENT,
				RankChoices.VICEPRESIDENT,
				RankChoices.TREASURER,
				RankChoices.SECRETARY,
				RankChoices.LIBRARIAN,
				RankChoices.WEBKEEPER
			)
		)
	
	def sync_permissions(self):
		"""
		This method is called every day, and whenever the member is saved.
		Automatically keeps permissions for the admin site up-to-date, based on the ranks that the member has.
		"""
		if self.user is None:
			# Can't do anything.
			return False
		
		# is_staff controls whether the user can log into the admin site.
		# Only committee and webkeepers get to do that.
		is_staff = False
		if self.is_committee():
			is_staff = True
		
		is_superuser = False
		if self.has_rank(RankChoices.WEBKEEPER) and self.is_valid_member():
			is_superuser = True
		
		if not is_staff:
			# If they can't log in to the admin site,
			# might as well remove all permissions.
			self.user.user_permissions.clear()
		else:
			# This should get fetch all permissions, except for those that add, change, or delete advanced models.
			permissions_to_set = Permission.objects.filter(
				Q(content_type__model__in=ADVANCED_MODELS, codename__startswith="view_") |
				~Q(content_type__model__in=ADVANCED_MODELS)
			)
			self.user.user_permissions.set(permissions_to_set)
		self.user.is_staff = is_staff
		self.user.is_superuser = is_superuser
		self.user.save()
		return True
	
	def get_borrow_records(self):
		"""
		Convenience method - Fetches all internal borrow_records that
		are linked to this Member.
		"""
		return BorrowRecord.objects.filter(borrower__internal_member=self)
	
	def get_active_borrow_records(self):
		"""
		Convenience method - Identical to the above except it only
		shows unreturned records.
		"""
		return self.get_borrow_records().filter(returned=False)


class PaymentChoices(models.TextChoices):
	NONE = "NONE", "-"
	CASH = "CASH", "Cash"
	CARD = "CARD", "Card"
	TRANSFER = "TFER", "Bank Transfer"


class Membership(models.Model):
	"""
	Stores information about a single membership purchased for a single member.
	"""
	member = models.ForeignKey("Member", on_delete=models.SET_NULL, null=True, related_name="memberships")
	date_purchased = models.DateField(default=timezone.now)
	guild_member = models.BooleanField()
	amount_paid = models.IntegerField()
	payment_method = models.CharField(max_length=5, choices=PaymentChoices.choices, default=PaymentChoices.NONE)
	expired = models.BooleanField(default=False)
	authorised_by = models.ForeignKey("Member", on_delete=models.SET_NULL, blank=True, null=True, related_name="authorised")
	
	def __str__(self):
		if self.member is not None:
			return f"Membership: {self.member.long_name} ({self.date_purchased.year})"
		else:
			return f"Membership: <deleted_member> ({self.date_purchased.year})"
	
	class Meta:
		ordering = ["-date_purchased"]


class RankChoices(models.TextChoices):
	EXCLUDED = 'EXCLUDED', 'Excluded'
	GATEKEEPER = 'GATEKEEPER', 'Gatekeeper'
	WEBKEEPER = 'WEBKEEPER', 'Webkeeper'
	COMMITTEE = 'COMMITTEE', 'Committee'
	LIFEMEMBER = 'LIFEMEMBER', 'Life Member'
	PRESIDENT = 'PRESIDENT', 'President'
	VICEPRESIDENT = 'VICEPRESIDENT', 'Vice-President'
	TREASURER = 'TREASURER', 'Treasurer'
	SECRETARY = 'SECRETARY', 'Secretary'
	LIBRARIAN = 'LIBRARIAN', 'Librarian'
	FRESHERREP = 'FRESHERREP', 'Fresher-Rep'
	OCM = 'OCM', 'OCM'
	IPP = 'IPP', 'IPP (Immediate Past President)'


class RankManager(models.Manager):
	"""
	Custom manager for ranks - this will annotate all Ranks with an easy to use "expired" field.
	"""
	def get_queryset(self):
		# Annotates the default queryset.
		return super().get_queryset().annotate(expired=Case(
			When(expired_date__lte=Now(), then=Value(True)),
			default=Value(False),
			output_field=models.BooleanField()
		))
	
	# This lets you use Ranks.objects.all_active/all_expired as a shortcut.
	def all_active(self):
		return self.all().filter(expired=False)
	
	def all_expired(self):
		return self.all().filter(expired=True)
	
	def get_committee(self):
		"""
		Returns a dictionary that maps the committee ranks into QuerySets of the members that have them.
		"""
		committee_data = {}
		for committee_rank in [
			RankChoices.PRESIDENT,
			RankChoices.VICEPRESIDENT,
			RankChoices.TREASURER,
			RankChoices.SECRETARY,
			RankChoices.LIBRARIAN,
			RankChoices.FRESHERREP,
			RankChoices.OCM,
			RankChoices.IPP,
		]:
			committee_data[committee_rank] = self.all_active().filter(rank_name=committee_rank).order_by("pk")
		return committee_data


class Rank(models.Model):
	"""
	Stores a rank for a Member, for granting permission and such.
	There are currently 13 hard-coded ranks.
	Each rank has an assignment date and expiry date.
	A rank stops granting privileges when current_date >= expiry_date.
	"""
	
	member = models.ForeignKey("Member", on_delete=models.CASCADE, related_name="ranks")
	rank_name = models.TextField(max_length=20, choices=RankChoices.choices)
	assigned_date = models.DateField(default=timezone.now)
	expired_date = models.DateField(blank=True, null=True)
	
	# Custom manager to help with quality of life
	objects = RankManager()
	
	def __str__(self):
		return f"Rank: {RankChoices[self.rank_name].label} for {self.member.long_name} {'(EXPIRED)' if self.is_expired else ''}"
	
	def save(self, *args, **kwargs):
		"""
		Whenever a Rank is saved, sync the permissions of the appropriate member.
		"""
		super().save(*args, **kwargs)
		self.member.sync_permissions()
	
	@property
	def is_expired(self):
		# A rank is expired if the expiry date <= today
		if self.expired_date is None:
			return False
		elif datetime.date.today() >= self.expired_date:
			return True
		else:
			return False
	
	def set_expired(self):
		# Set the expiry date to today.
		self.expired_date = datetime.date.today()
		self.save()


class FinanceRecordManager(models.Manager):
	"""
	Manager for the Finance Records.
	"""
	@staticmethod
	def generate_code():
		return generate_reference_code()


class FinanceRecord(models.Model):
	"""
	A model for storing data about electronic bank transfers to the Unigames account.
	"""
	member = models.ForeignKey(
		Member,
		on_delete=models.SET_NULL, null=True, blank=True,
		related_name="transfers",
		help_text="The member who made the purchase."
	)
	purchase_type = models.CharField(
		max_length=200, blank=True,
		help_text="A brief description of the purchase."
	)
	reference_code = models.CharField(
		max_length=20,
		help_text="A unique identifier for this payment."
	)
	amount = models.DecimalField(
		max_digits=5, decimal_places=2,
		help_text="The amount transferred."
	)
	added_at = models.DateTimeField(
		auto_now_add=True,
		help_text="Date and time payment was made."
	)
	added_by = models.ForeignKey(
		Member,
		on_delete=models.SET_NULL, null=True, blank=True,
		related_name="transfers_authorised",
		help_text="The Gatekeeper who facilitated the transfer."
	)
	resolved = models.BooleanField(
		help_text="Check this when the transaction has been resolved / verified.",
		default=False,
	)
	objects = FinanceRecordManager()

	def __str__(self):
		if self.member is not None:
			return f"{self.member.long_name}: {self.amount} ({self.reference_code})"
		else:
			return f"<deleted member>: {self.amount} ({self.reference_code})"
