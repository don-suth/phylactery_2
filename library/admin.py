from django.contrib import admin
from django.db import models
from django import forms
from dal.forms import FutureModelForm
from dal.autocomplete import ModelSelect2Multiple
from dal_select2_taggit.widgets import TaggitSelect2

from .models import Item, LibraryTag, BorrowerDetails, BorrowRecord, Reservation


class ItemModelForm(FutureModelForm):
	class Meta:
		model = Item
		fields = [
			"name", "slug",
			"image",
			"description", "condition", "notes",
			"base_tags", "computed_tags",
			"min_players", "max_players",
			"min_play_time", "max_play_time", "average_play_time",
			"is_borrowable", "is_high_demand"
		]
		widgets = {
			"description": forms.Textarea(
				attrs={
					"style": "font-family: monospace; width: 100%;",
					
				}
			),
			"notes": forms.Textarea(
				attrs={
					"style": "font-family: monospace; width: 100%;",
					
				}
			),
			"condition": forms.Textarea(
				attrs={
					"style": "font-family: monospace; width: 100%;",
					
				}
			),
			"base_tags": TaggitSelect2(
				url="library:autocomplete_tag",
				attrs={
					"style": "width: 100%;",
				}
			),
		}
		help_texts = {
			"base_tags": "",
			"computed_tags": ""
		}


class ReservationModelForm(FutureModelForm):
	class Meta:
		model = Reservation
		fields = "__all__"
		widgets = {
			"reserved_items": ModelSelect2Multiple(
				url="library:autocomplete_item",
			)
		}


class ItemAdmin(admin.ModelAdmin):
	form = ItemModelForm
	prepopulated_fields = {"slug": ("name",)}
	search_fields = ["name",]
	fields = [
		"name", "slug",
		"image",
		"description", "condition", "notes",
		("base_tags", "computed_tags"),
		"min_players", "max_players",
		"min_play_time", "max_play_time", "average_play_time",
		"is_borrowable", "is_high_demand",
	]
	readonly_fields = ["computed_tags"]


class BorrowRecordsInline(admin.TabularInline):
	model = BorrowRecord
	extra = 0
	can_delete = False
	
	formfield_overrides = {
		models.TextField: {
			"widget": forms.Textarea(
				attrs={
					"cols": 40,
					"rows": 3
				}
			)
		}
	}
	
	readonly_fields = [
		"item", "borrower"
	]
	
	fields = [
		"item", "borrower",
		"due_date", "returned_datetime", "return_authorised_by", "comments", "verified_returned"
	]


class BorrowerDetailsAdmin(admin.ModelAdmin):
	list_display = [
		"__str__", "borrower_name", "borrowed_datetime", "is_external"
	]
	readonly_fields = [
		"is_external", "borrower_name", "internal_member", "borrowed_datetime", "borrow_authorised_by"
	]
	inlines = [BorrowRecordsInline]
	
	def get_fields(self, request, obj=None):
		fields = [
			"is_external", "borrower_name",
			"internal_member",
			"borrower_address",
			"borrower_phone",
			"borrowed_datetime", "borrow_authorised_by"
		]
		if obj is not None:
			if obj.is_external:
				fields.remove("internal_member")
		return fields


class LibraryTagAdmin(admin.ModelAdmin):
	prepopulated_fields = {"slug": ("name",)}
	search_fields = ["name",]
	autocomplete_fields = ["parents",]
	

class ReservationAdmin(admin.ModelAdmin):
	readonly_fields = [
		"is_external", "requestor_name", "internal_member",
		"submitted_datetime", "status_update_datetime"
	]
	
	form = ReservationModelForm
	
	def get_fields(self, request, obj=None):
		fields = [
			"is_external", "internal_member",
			"requestor_name",
			"requestor_email",
			"requestor_phone",
			"requested_date_to_borrow",
			"requested_date_to_return",
			"additional_details",
			"reserved_items",
			"librarian_comments",
			"approval_status",
			"is_active",
			"borrower",
			("submitted_datetime", "status_update_datetime")
		]
		if obj is not None:
			if obj.is_external:
				fields.remove("internal_member")
		return fields


admin.site.register(Item, ItemAdmin)
admin.site.register(BorrowerDetails, BorrowerDetailsAdmin)
admin.site.register(LibraryTag, LibraryTagAdmin)
admin.site.register(Reservation, ReservationAdmin)
