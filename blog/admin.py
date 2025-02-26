from django.contrib import admin
from django.db import models
from django.forms.widgets import Textarea
from .models import MailingList, BlogPost, EmailOrder


class MarkdownWidget(Textarea):
	"""
	Custom widget for Markdown fields.
	Sets the font to a monospace font and the width to 100%.
	"""
	def __init__(self):
		super().__init__(attrs={"style": "width: 100%; font-family: monospace, monospace;"})


class EmailOrderAdmin(admin.TabularInline):
	model = EmailOrder
	extra = 0
	autocomplete_fields = ["mailing_lists"]


class BlogPostAdmin(admin.ModelAdmin):
	model = BlogPost
	
	list_display = ["title", "publish_on", "author", "is_published_bool"]
	search_fields = ["title", "author", "body"]
	
	inlines = [EmailOrderAdmin]
	
	# Set the slug field to generate automatically from the title.
	prepopulated_fields = {"slug_title": ("title",)}
	
	# Set the TextFields to use our custom widget.
	formfield_overrides = {
		models.TextField: {"widget": MarkdownWidget}
	}
	
	# Display pretty checkboxes to show whether something is published
	@admin.display(description="Is Published?", boolean=True)
	def is_published_bool(self, obj):
		return obj.is_published


class MailingListAdmin(admin.ModelAdmin):
	model = MailingList
	exclude = ["members"]
	search_fields = ["name"]


admin.site.register(MailingList, MailingListAdmin)
admin.site.register(BlogPost, BlogPostAdmin)