from django.contrib import admin

from .models import Member, Membership, Rank


class RankInline(admin.TabularInline):
	model = Rank
	extra = 1


class MembershipInline(admin.TabularInline):
	model = Membership
	extra = 0
	fk_name = "member"
	fields = ("date_purchased", "phone_number", "guild_member", "amount_paid", "expired", "authorised_by")


class MemberAdmin(admin.ModelAdmin):
	inlines = [RankInline, MembershipInline]


admin.site.register(Member, MemberAdmin)

# Register your models here.
