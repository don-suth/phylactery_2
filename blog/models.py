from django.db import models
from django.db.models import Case, When, Value
from django.db.models.functions import Now
from django.urls import reverse
from django.utils import timezone

from members.models import Member


class BlogPostManager(models.Manager):
	"""
	Custom manager for the BlogPost model.
	This will annotate all objects with a "published" field,
	for convenience.
	"""
	def get_queryset(self):
		# Annotates the default queryset.
		return super().get_queryset().annotate(
			published=Case(
				When(
					publish_on__lte=Now(),
					then=Value(True)
				),
				default=Value(False),
				output_field=models.BooleanField()
			)
		)


class BlogPost(models.Model):
	"""
	A model for Blog Posts.
	Each one represents a single post.
	"""
	
	title = models.CharField(
		max_length=200,
		help_text="The title of this Blog Post."
	)
	slug_title = models.SlugField(
		max_length=200,
		unique=True,
		help_text="An automatically generated, URL-safe title. Generally you don't edit these once the post is created.",
	)
	short_description = models.CharField(
		max_length=300,
		default="",
		help_text="A short summary of the post to serve as the preview of the contents. "
		"Displayed on the ListView and in Emails. Markdown not enabled."
	)
	author = models.CharField(
		max_length=200,
		help_text="The author of the post. (e.g. 'Donald Sutherland', or 'Unigames Committee')",
	)
	publish_on = models.DateTimeField(
		blank=True,
		null=True,
		default=None,
		help_text="The date and time at which the post will become published. "
		"If this is set to a future date, the post will be hidden until then. "
		"If left blank, this will never be published (basically saved as a draft.)"
	)
	body = models.TextField(
		blank=True,
		help_text="The body of the post. Markdown enabled."
	)
	
	# Apply custom manager above
	objects = BlogPostManager()
	
	@property
	def is_published(self) -> bool:
		"""
		Returns True if the post is published. False otherwise.
		"""
		if self.publish_on is None:
			return False
		elif self.publish_on > timezone.now():
			return False
		else:
			return True
	
	@property
	def get_pretty_timestamp(self):
		"""
		Returns a pretty string, detailing when the post was published.
		"""
		if self.is_published:
			now = timezone.now()
			days_difference = (now.date() - self.publish_on.date()).days
			if days_difference == 0:
				return "Today"
			elif days_difference == 1:
				return "Yesterday"
			elif (days_difference > 1) and (days_difference < 7):
				return f"{days_difference} days ago"
			else:
				return self.publish_on.date().strftime("%d/%m/%y")
		else:
			if self.publish_on is None:
				return "Not published"
			else:
				return self.publish_on.date().strftime("Set to be published: %d/%m/%y")
	
	def __str__(self):
		if self.is_published:
			return self.title
		else:
			return f"{self.title} (not published)"
	
	def get_absolute_url(self):
		"""
		Returns the URL to view this post.
		"""
		return reverse("blog:detail", args=[self.slug_title])

	
class MailingList(models.Model):
	"""
	Previously called MemberFlags - Members can self-assign these to "subscribe" to various mailing lists.
	Blog Post writers can email them out to all Members in one or more of these lists.
	"""
	name = models.CharField(
		max_length=20,
		help_text="The name for this Mailing List. e.g. Magic, Wargaming, 2023 Freshers, etc."
	)
	description = models.CharField(
		max_length=200,
		help_text="A brief description of the mailing list. e.g. News about Major Unigames events."
	)
	verbose_description = models.CharField(
		max_length=200,
		help_text="This text will appear as a prompt on the Membership forms. e.g. 'I want to receive news about MtG events.'"
	)
	is_active = models.BooleanField(
		default=True,
		help_text="This controls whether people are able to subscribe to this group."
	)
	
	members = models.ManyToManyField(
		to="members.Member",
		related_name="mailing_lists",
	)
	
	def __str__(self):
		return f"{self.name} {'(inactive)' if self.is_active is False else ''}"
	

class EmailOrder(models.Model):
	"""
	Tracks a specific request to email out a BlogPost to a group of MailingLists.
	A Celery Task will check these every so often.
	If it finds any EmailOrders that:
		- aren't completed
		- are linked to a BlogPost that is published
	Then it will send out that post as an Email to all selecting MailingLists.
	"""
	
	# The BlogPost to email
	blog_post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name="email_orders")
	
	# The lists to email it to
	# If no lists are sent, then it will send to all members.
	mailing_lists = models.ManyToManyField(MailingList, related_name="email_orders")
	
	# Has this been done?
	email_sent = models.BooleanField(default=False)
	
	@property
	def is_ready(self):
		# Returns True if the linked BlogPost is published,
		# there are members to send it to, and we haven't
		# done this already.
		return (
			self.email_sent is False
			and self.blog_post.is_published is True
			and self.get_members_to_send_to().count() != 0
		)
	
	def get_members_to_send_to(self):
		# Returns a QuerySet of Members that emails should be sent to.
		if self.mailing_lists.count() == 0:
			# Send this email to all Members that have opted in to emails.
			qs = Member.objects.filter(optional_emails=True)
		else:
			qs = Member.objects.filter(mailing_lists__email_orders=self, optional_emails=True)
		return qs
	
	def __str__(self):
		return f"Email Order for {self.blog_post.title}"
