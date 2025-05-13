from django.contrib import admin

from blog.models import MailingList
from .models import Member, Membership, Rank, FinanceRecord, RankChoices


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
	fields = ("date_purchased", "guild_member", "amount_paid", "payment_method", "expired", "authorised_by")
	readonly_fields = ("payment_method",)


class MemberGatekeeperFilter(admin.SimpleListFilter):
	"""
		Adds a filter to the Member list in the admin to filter based
		on gatekeeper status.
	"""
	title = "Gatekeeper status:"
	parameter_name = "gatekeeper"
	
	def lookups(self, request, model_admin):
		return (
			("gate", "Gatekeepers"),
			("not_gate", "Non-Gatekeepers")
		)
	
	def queryset(self, request, queryset):
		active_gatekeeper_ranks = Rank.objects.filter(expired=False, rank_name=RankChoices.GATEKEEPER)
		match self.value():
			case "gate":
				return queryset.filter(ranks__in=active_gatekeeper_ranks)
			case "not_gate":
				return queryset.exclude(ranks__in=active_gatekeeper_ranks)


class MembershipStatusFilter(admin.SimpleListFilter):
	"""
		Adds a filter to the Member list in the admin to filter based
		on membership status.
	"""
	title = "membership status:"
	parameter_name = "membership_status"
	
	def lookups(self, request, model_admin):
		return (
			("financial", "Financial Members"),
			("non_financial", "Non-Members"),
		)
	
	def queryset(self, request, queryset):
		match self.value():
			case "financial":
				return queryset.filter(memberships__expired=False)
			case "non_financial":
				return queryset.exclude(memberships__expired=False)


class MemberAdmin(admin.ModelAdmin):
	list_display = ["__str__", "pronouns", "join_date", "is_fresher_bool", "notes"]
	search_fields = ["short_name", "long_name"]
	list_filter = (MemberGatekeeperFilter, MembershipStatusFilter)
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
