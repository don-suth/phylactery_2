from django.contrib import admin

from blog.models import MailingList
from .models import Member, Membership, Rank, FinanceRecord


class RankInline(admin.TabularInline):
	model = Rank
	extra = 0


class MailingListInline(admin.TabularInline):
	model = MailingList.members.through
	extra = 0


class MembershipInline(admin.TabularInline):
	model = Membership
	extra = 0
	fk_name = "member"
	fields = ("date_purchased", "guild_member", "amount_paid", "expired", "authorised_by")


class MemberAdmin(admin.ModelAdmin):
	list_display = ["__str__", "pronouns", "join_date", "is_fresher_bool", "notes"]
	search_fields = ["short_name", "long_name"]
	inlines = [RankInline, MembershipInline, MailingListInline]
	
	@admin.display(description="Fresher?", boolean=True)
	def is_fresher_bool(self, obj):
		return obj.is_fresher()


@admin.action(description="Mark selected records as resolved")
def mark_resolved(modeladmin, request, queryset):
	queryset.update(resolved=True)


class FinanceRecordAdmin(admin.ModelAdmin):
	list_display = ["reference_code", "amount", "added_at", "resolved", "member", "added_by"]
	list_filter = ["resolved"]
	show_facets = admin.ShowFacets.ALWAYS
	actions = [mark_resolved]
	ordering = ["resolved", "added_at"]


admin.site.register(Member, MemberAdmin)
admin.site.register(Membership)
admin.site.register(FinanceRecord, FinanceRecordAdmin)
