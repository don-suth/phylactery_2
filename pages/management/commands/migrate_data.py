import json
from accounts.models import UnigamesUser, create_fresh_unigames_user
from blog.models import MailingList, BlogPost
from library.models import Item, LibraryTag, BorrowerDetails, BorrowRecord, Reservation
from members.models import Member, Membership, Rank, RankChoices
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.core.validators import validate_email
from django.db import connection
from collections import defaultdict
from datetime import datetime

"""
This program will be used to import data from the old website into the new one.

We will skip:
	- Admin Log Entries
		- admin.logentry
	- Auth as a whole (people will need to reset passwords anyway)
		- auth.group
		- auth.permission
		- auth.user
	- Blog Email Orders (No need, except for archival purposes)
		- blog.emailorder
	- ContentTypes
		- contenttypes.contenttypes
	- Celery stuff as a whole (can be easily re-added afterwards)
		- django_celery_beat.crontabschedule
		- django_celery_beat.intervalschedule
		- django_celery_beat.periodictask
		- django_celery_beat.periodictasks
	- Library Computed Tags (can re-compute them)
		- library.itemcomputedtags
	- Member Ranks (Previously, the ranks were objects in the database. Now they are not.)
		- members.ranks
	- Sessions (keeping these is dangerous)
		- sessions.session
	- Sites (easier to add manually)
		- sites.site
	
	
We will import:
	- Blog Posts
		- blog.blogpost - Done!
	- Library (almost everything)
		- library.borrowrecord
		- library.externalborrowingform
		- library.externalborrowingitemrecord
		- library.item - Done!
		- library.itembasetags - Done!
		- library.tagparent - Done!
	- Members
		- members.member - Done!
		- members.memberflag - Done!
			- Reworked to be under Blog
		- members.membership - Done!
		- members.rankassignments - Done!
			- Reworked to be "ranks"
	- Taggit Tags
		- taggit.tag - Done!
		- taggit.taggeditem - Done!
	

"""

BASE_PATH = settings.BASE_DIR / "pretty_models"


APPROVAL_STATUS = {
	"U": "?",
	"D": "X",
	"A": "A",
	"C": "!",
}

def convert_to_date(date_str):
	if date_str is None:
		return None
	return datetime.strptime(date_str, "%Y-%m-%d")


class Command(BaseCommand):
	def handle(self, *args, **options):
		self.import_model_data()
		self.import_initial_library()
		self.import_members()
		self.import_blog()
		self.import_final_library()
	
	def import_model_data(self):
		old_db_data = input()
		print(f"Received {len(old_db_data)} chars of input.")
		old_db_data = json.loads(old_db_data)
		
		self.models = defaultdict(list)
		for entry in old_db_data:
			model_type = entry["model"]
			self.models[model_type].append(entry)
		
	
	def import_final_library(self):
		"""
		Continuing on from import_members
		Steps:
			1) Convert external borrowing forms to reservations and borrowerdetails and import them.
			2) Convert external borrowing item record into borrowrecords.
			3) Attempt to group borrow records into borrowerdetails, and import them
		"""
		json_objects = self.models["library.externalborrowingform"]
		for external_borrowing_form in json_objects:
			self.import_external_borrowing_form(external_borrowing_form["pk"], external_borrowing_form["fields"])
		self.fix_pk_sequence(Reservation)
		
		external_item_records_by_form_pk = defaultdict(list)
		json_objects = self.models["library.externalborrowingitemrecord"]
		for external_item_record in json_objects:
			external_item_records_by_form_pk[external_item_record["fields"]["form"]].append(external_item_record)
		
		for reservation_pk, external_borrowing_records in external_item_records_by_form_pk.items():
			reservation = Reservation.objects.get(pk=reservation_pk)
			borrower_detail_address = "<migrated data>"
			borrower_detail_phone = reservation.requestor_phone
			borrower_detail_borrowed_date = None
			borrower_detail_authed_by_pk = None
			current_borrower_details = None
			self.stdout.write(f"Adding borrow records for reservation {reservation_pk}")
			for record in external_borrowing_records:
				item = Item.objects.get(pk=record["fields"]["item"])
				reservation.reserved_items.add(item)
				if (
						record["fields"]["borrower_name"] == ""
						or record["fields"]["auth_gatekeeper_borrow"] == ""
						or record["fields"]["date_borrowed"] == ""
				):
					# Skip adding a record
					self.stdout.write(f"- Skipped adding record for {item}")
					continue
				else:
					if (
							current_borrower_details is None
							or current_borrower_details.borrower_name != record["fields"]["borrower_name"]
							or borrower_detail_borrowed_date != record["fields"]["date_borrowed"]
							or borrower_detail_authed_by_pk != record["fields"]["auth_gatekeeper_borrow"]
					):
						# Make a new borrower details object
						borrower_detail_authed_by_pk = record["fields"]["auth_gatekeeper_borrow"]
						borrow_authed_by_qs = Member.objects.filter(pk=borrower_detail_authed_by_pk)[0:1]
						if borrow_authed_by_qs.exists():
							borrow_authed_by = borrow_authed_by_qs.get().long_name
						else:
							borrow_authed_by = "<Internal Member record deleted>"
						borrower_detail_borrowed_date = record["fields"]["date_borrowed"]
						current_borrower_details = BorrowerDetails.objects.create(
							is_external=True,
							internal_member=None,
							borrower_name=record["fields"]["borrower_name"],
							borrower_address=borrower_detail_address,
							borrower_phone=borrower_detail_phone,
							borrowed_datetime=borrower_detail_borrowed_date + "T04:00:00Z",
							borrow_authorised_by=borrow_authed_by,
						)
				# Add the Borrow Record
				if record["fields"]["date_returned"]:
					returned_datetime = record["fields"]["date_returned"] + "T04:00:00Z"
					verified_returned = True
				else:
					returned_datetime = ""
					verified_returned = False
				if record["fields"]["auth_gatekeeper_return"]:
					return_authed_by_qs = Member.objects.filter(pk=record["fields"]["auth_gatekeeper_return"])[0:1]
					if return_authed_by_qs.exists():
						return_authed_by = return_authed_by_qs.get().long_name
					else:
						return_authed_by = "<Internal Member record deleted>"
				else:
					return_authed_by = ""
				
				BorrowRecord.objects.create(
					item=item,
					borrower=current_borrower_details,
					borrowed_datetime=current_borrower_details.borrowed_datetime,
					borrow_authorised_by=current_borrower_details.borrow_authorised_by,
					due_date=reservation.requested_date_to_return,
					returned_datetime=returned_datetime,
					return_authorised_by=return_authed_by,
					comments="<migrated data>",
					verified_returned=verified_returned,
				)
				self.stdout.write(f"- Added external borrow record for {item}")
	
			
		
		# Group borrow records into borrower details, and import them.
		# For this, we assume that any borrow records that have the same:
		# - borrowing member
		# - address
		# - phone number
		# - borrow date
		# - AND authorising gatekeeper
		# are all part of the same borrowing instance
		borrow_records_by_instance = defaultdict(list)
		
		json_objects = self.models["library.borrowrecord"]
		for borrow_record in json_objects:
			key = f"{borrow_record['fields']['borrowing_member']}-{borrow_record['fields']['member_address']}-{borrow_record['fields']['member_phone_number']}-{borrow_record['fields']['date_borrowed']}-{borrow_record['fields']['auth_gatekeeper_borrow']}"
			borrow_record["key"] = key
			borrow_records_by_instance[key].append(borrow_record)
		for key, records in borrow_records_by_instance.items():
			first_record_fields = records[0]["fields"]
			borrowing_member_qs = Member.objects.filter(pk=first_record_fields["borrowing_member"])[0:1]
			if borrowing_member_qs.exists():
				internal_member = borrowing_member_qs.get()
				borrower_name = internal_member.long_name
			else:
				internal_member = None
				borrower_name = "<Internal Member record deleted>"
			borrower_address = first_record_fields["member_address"]
			borrower_phone = first_record_fields["member_phone_number"]
			borrowed_datetime = first_record_fields["date_borrowed"]
			if borrowed_datetime:
				borrowed_datetime += "T04:00:00Z"
			borrow_authorised_by_qs = Member.objects.filter(pk=first_record_fields["auth_gatekeeper_borrow"])[0:1]
			if borrow_authorised_by_qs.exists():
				borrow_authorised_by = borrow_authorised_by_qs.get().long_name
			else:
				borrow_authorised_by = "<Internal Member record deleted>"
			borrower_details = BorrowerDetails.objects.create(
				is_external=False,
				internal_member=internal_member,
				borrower_name=borrower_name,
				borrower_address=borrower_address,
				borrower_phone=borrower_phone,
				borrowed_datetime=borrowed_datetime,
				borrow_authorised_by=borrow_authorised_by,
			)
			for record in records:
				self.import_borrow_record(borrower_details, record["fields"])
				
			
			
	
	def import_blog(self):
		"""
		Just a simple one here, just importing the blogposts.
		"""
		json_objects = self.models["blog.blogpost"]
		for blogpost in json_objects:
			self.import_blog_post(pk=blogpost["pk"], fields=blogpost["fields"])
		self.fix_pk_sequence(BlogPost)
	
	def import_members(self):
		"""
		Continuing on from import_initial_library
		Steps:
			1) Import members
				a) Create e member object for them
				b) Create a blank user object for them.
				c) In the event that their email is not valid (ie. a student email) then we don't create a user for them.
			2) Import memberships
			3) Import rank assignments
			3) Import mailing lists / memberflags
			4) Sync all member permissions
			Then we can work on the rest of the Library stuff
		"""
		
		# Step 1: Import Members
		json_objects = self.models["members.member"]
		for member in json_objects:
			self.import_member(pk=member["pk"], fields=member["fields"])
		self.fix_pk_sequence(Member)
		
		# Step 2: Import Memberships
		json_objects = self.models["members.membership"]
		for membership in json_objects:
			self.import_membership(pk=membership["pk"], fields=membership["fields"])
		self.fix_pk_sequence(Membership)
		
		# Step 3: Import Ranks
		self.ranks = {
			2: RankChoices.EXCLUDED,
			3: RankChoices.GATEKEEPER,
			4: RankChoices.WEBKEEPER,
			5: RankChoices.COMMITTEE,
			7: RankChoices.LIFEMEMBER,
			8: RankChoices.PRESIDENT,
			9: RankChoices.VICEPRESIDENT,
			10: RankChoices.SECRETARY,
			11: RankChoices.TREASURER,
			12: RankChoices.LIBRARIAN,
			13: RankChoices.FRESHERREP,
			14: RankChoices.OCM,
			15: RankChoices.IPP
		}
		
		json_objects = self.models["members.rankassignments"]
		for rank in json_objects:
			self.import_ranks(pk=rank["pk"], fields=rank["fields"])
		self.fix_pk_sequence(Rank)
		
		# Step 4: Import mailing lists
		json_objects = self.models["members.memberflag"]
		for mailing_list in json_objects:
			self.import_mailing_list(pk=mailing_list["pk"], fields=mailing_list["fields"])
		self.fix_pk_sequence(MailingList)
		
		# Step 5: Sync member permissions.
		self.stdout.write("Syncing user permissions: ", ending="")
		for member in Member.objects.all():
			member.sync_permissions()
			self.stdout.write(".", ending="")
			self.stdout.flush()
		self.stdout.write(" Done!")
	
	def import_initial_library(self):
		"""
		Steps:
			1) Import all taggit tags into LibraryTags
			2) Import the TagParents
			3) Add the Item Type tags (afterward, so the PKs don't conflict)
			4) Import the Items
			5) Add the appropriate tags onto Library Items (only base tags)
			6) Save all Items.
			At this point we will need to add Members, so that we can add BorrowRecords.
		"""
		
		# Step 1:  Import all taggit tags into LibraryTags
		json_objects = self.models["taggit.tag"]
		for library_tag in json_objects:
			self.import_library_tag(pk=library_tag["pk"], fields=library_tag["fields"])
		self.fix_pk_sequence(LibraryTag)
		
		# Step 2: Import the tag parents
		json_objects = self.models["library.tagparent"]
		for tag_parent in json_objects:
			child_tag = LibraryTag.objects.get(pk=tag_parent["fields"]["child_tag"])
			child_tag.parents.set(tag_parent["fields"]["parent_tag"])
			self.stdout.write(f"Setting parents for {child_tag.name}")
		
		# Step 3: Add the Item-type tags.
		self.item_types = {
			"BK": LibraryTag.objects.create(name="Item Type: Book", is_item_type=True),
			"BG": LibraryTag.objects.create(name="Item Type: Board Game", is_item_type=True),
			"CG": LibraryTag.objects.create(name="Item Type: Card Game", is_item_type=True),
			"??": LibraryTag.objects.create(name="Item Type: Other", is_item_type=True),
		}
		for item_type in self.item_types.values():
			item_type.full_clean()
		
		# Step 4: Import the Items
		json_objects = self.models["library.item"]
		for library_item in json_objects:
			self.import_library_item(pk=library_item["pk"], fields=library_item["fields"])
		self.fix_pk_sequence(Item)
		
		# Step 5: Apply base tags to Items.
		# Because of the previous implementation, we have to look
		# at two files simultaneously to figure out which tags should go where.
		json_objects = self.models["library.itembasetags"]
		
		# Construct a dictionary, mapping the pk of the "item_base_tags" object to the Item itself.
		# (Yes, this system was stupid. In my defense, so was I.)
		item_lookup = {}
		for item_base_tags in json_objects:
			item_lookup[item_base_tags["pk"]] = item_base_tags["fields"]["item"]
		# Now we can continue.
		json_objects = self.models["taggit.taggeditem"]
		invalid_content_types = defaultdict(list)
		for tagged_item in json_objects:
			tag_pk = tagged_item["fields"]["tag"]
			content_type = tagged_item["fields"]["content_type"]
			object_id = tagged_item["fields"]["object_id"]
			# The content_type is what matters here. We're looking for 12, and we ignore 13.
			# A tag shouldn't have been tagged to anything else.
			if content_type == 12:
				item = Item.objects.get(pk=item_lookup[object_id])
				tag = LibraryTag.objects.get(pk=tag_pk)
				item.base_tags.add(tag)
				self.stdout.write(f"Tagged {item.name} with {tag.name}")
			elif content_type == 13:
				pass
			else:
				invalid_content_types[content_type].append((tag_pk, content_type, object_id))
		if invalid_content_types:
			self.stdout.write(f"Warning: {invalid_content_types=}")
		
		# Step 6: Save all Items to regenerate all Tag data properly.
		self.stdout.write("Re-saving all items: ", ending="")
		for item in Item.objects.all():
			item.save()
			self.stdout.write(".", ending="")
			self.stdout.flush()
		self.stdout.write(" Done!")
	
	def import_library_tag(self, pk, fields):
		tag_data = {
			"pk": pk,
			"name": fields["name"],
			"slug": fields["slug"],
		}
		new_tag = LibraryTag.objects.create(**tag_data)
		new_tag.full_clean()
		self.stdout.write(f"Added library.librarytag: {new_tag.name}")
	
	def import_library_item(self, pk, fields):
		item_data = {
			"pk": pk,
			"name": fields["name"],
			"slug": fields["slug"],
			"description": fields["description"],
			"condition": fields["condition"],
			"notes": fields["notes"],
			"is_borrowable": fields["is_borrowable"],
			"is_high_demand": fields["high_demand"],
			"min_players": fields["min_players"],
			"max_players": fields["max_players"],
			"min_play_time": fields["min_play_time"],
			"max_play_time": fields["max_play_time"],
			"average_play_time": fields["average_play_time"],
			"image": fields["image"],
		}
		new_item = Item.objects.create(**item_data)
		new_item.full_clean()
		new_item.base_tags.add(self.item_types[fields["type"]])
		self.stdout.write(f"Added library.item: {new_item.name}")
	
	def import_member(self, pk, fields):
		member_data = {
			"pk": pk,
			"short_name": fields["preferred_name"],
			"long_name": f'{fields["preferred_name"]} {fields["last_name"]}',
			"pronouns": fields["pronouns"],
			"student_number": fields["student_number"],
			"join_date": fields["join_date"],
			"notes": fields["notes"],
			"optional_emails": fields["receive_emails"]
		}
		email_address = fields["email_address"]
		make_user = True
		try:
			validate_email(email_address)
		except ValidationError:
			make_user = False
		if "@student" in email_address:
			make_user = False
		if UnigamesUser.objects.filter(email=email_address).exists():
			make_user = False
		
		if make_user:
			
			member_data["user"] = create_fresh_unigames_user(email_address)
		else:
			member_data["user"] = None
		
		new_member = Member.objects.create(**member_data)
		new_member.full_clean(exclude=["pronouns"])
		self.stdout.write(f"Added members.member: {new_member.long_name}{' - skipped creating user' if make_user is False else ''}")
	
	def import_membership(self, pk, fields):
		member = Member.objects.filter(pk=fields["member"]).first()
		auth_by = Member.objects.filter(pk=fields["authorising_gatekeeper"]).first()
		membership_data = {
			"pk": pk,
			"member": member,
			"date_purchased": convert_to_date(fields["date"]),
			"guild_member": fields["guild_member"],
			"amount_paid": fields["amount_paid"],
			"expired": fields["expired"],
			"authorised_by": auth_by
		}
		new_membership = Membership.objects.create(**membership_data)
		new_membership.full_clean(exclude=["authorised_by"])
		self.stdout.write(f"Added members.membership: {new_membership}")
	
	def import_ranks(self, pk, fields):
		rank_data = {
			"pk": pk,
			"member": Member.objects.get(pk=fields["member"]),
			"rank_name": self.ranks[fields["rank"]],
			"assigned_date": convert_to_date(fields["assignment_date"]),
			"expired_date": convert_to_date(fields["expired_date"]),
		}
		new_rank = Rank.objects.create(**rank_data)
		new_rank.full_clean()
		self.stdout.write(f"Added {new_rank}")
		
	def import_mailing_list(self, pk, fields):
		mailing_list_data = {
			"pk": pk,
			"name": fields["name"],
			"description": "",
			"verbose_description": fields["description"],
			"is_active": fields["active"],
		}
		new_mailing_list = MailingList.objects.create(**mailing_list_data)
		self.stdout.write(f"Added blog.mailinglist: {new_mailing_list.name}")
		new_mailing_list.members.set(fields["member"])
		self.stdout.write(f"  - set {len(fields['member'])} members for {new_mailing_list.name}")
		
	def import_blog_post(self, pk, fields):
		blogpost_data = {
			"pk": pk,
			"title": fields["title"],
			"slug_title": fields["slug_title"],
			"short_description": fields["short_description"],
			"author": fields["author"],
			"publish_on": fields["publish_on"],
			"body": fields["body"]
		}
		new_blogpost = BlogPost.objects.create(**blogpost_data)
		self.stdout.write(f"Added blog.blogpost: {new_blogpost.slug_title}")
	
	def import_borrow_record(self, borrower_details, fields):
		return_authorised_by_qs = Member.objects.filter(pk=fields["auth_gatekeeper_return"])[0:1]
		if return_authorised_by_qs.exists():
			return_authorised_by = return_authorised_by_qs.get().long_name
		else:
			return_authorised_by = "<Internal Member record deleted>"
		
		borrow_record_data = {
			"item": Item.objects.get(pk=fields["item"]),
			"borrower": borrower_details,
			"borrowed_datetime": borrower_details.borrowed_datetime,
			"borrow_authorised_by": borrower_details.borrow_authorised_by,
			"due_date": fields["due_date"],
			"returned_datetime": fields["date_returned"],
			"comments": "<migrated data>",
			"verified_returned": fields["verified_returned"],
			"return_authorised_by": return_authorised_by,
		}
		if borrow_record_data["returned_datetime"]:
			borrow_record_data["returned_datetime"] += "T04:00:00Z"
		new_borrow_record = BorrowRecord.objects.create(**borrow_record_data)
		self.stdout.write(f"Added library.borrowrecord: {new_borrow_record.pk}")
	
	def import_external_borrowing_form(self, pk, fields):
		# Convert external borrowing forms into reservations
		reservation_data = {
			"pk": pk,
			"is_external": True,
			"internal_member": None,
			"requestor_name": fields["applicant_name"],
			"requestor_email": fields["contact_email"],
			"requestor_phone": fields["contact_phone"],
			"requested_date_to_borrow": fields["requested_borrow_date"],
			"requested_date_to_return": fields["requested_borrow_date"],
			"submitted_datetime": fields["form_submitted_date"],
			"approval_status": APPROVAL_STATUS[fields["form_status"]],
			"additional_details": "<migrated data>\n",
			"status_update_datetime": fields["form_submitted_date"],
			"librarian_comments": fields["librarian_comments"],
			"is_active": False,
			"borrower": None,
		}
		if fields["applicant_org"]:
			reservation_data["additional_details"] += f"Organisation: {fields['applicant_org']}\n"
		reservation_data["additional_details"] += f"------\n{fields['event_details']}\n"
		Reservation.objects.create(**reservation_data)
		self.stdout.write(f"Added library.reservation from external borrowing form {pk}")
	
	def fix_pk_sequence(self, app):
		"""
		When creating rows in Postgres, if you specify what their primary key is,
		the sequence that auto-generates new primary keys gets out of sync.
		
		Using this function after manually adding rows will reset the sequence
		for a given app and allow automatic PKs to work without conflicts again.
		"""
		sequence_sql = connection.ops.sequence_reset_sql(no_style(), [app])
		with connection.cursor() as cursor:
			for sql in sequence_sql:
				cursor.execute(sql)
