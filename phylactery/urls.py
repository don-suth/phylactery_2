from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static

# This is to ensure that all attempts to access the admin
# go through the regular login view first.
# Otherwise, people would need to login with a username, not an email.
from allauth.account.decorators import secure_admin_login
admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
	path("admin/", admin.site.urls),
	path("accounts/", include("allauth.urls")),
	path("members/", include("members.urls")),
	path("library/", include("library.urls")),
	path("blog/", include("blog.urls")),
	path("controlpanel/", include("control_panel.urls")),
	path("door/", include("door.urls")),
	path("", include("pages.urls")),
]

if settings.DEBUG:
	import debug_toolbar
	
	urlpatterns = [
		path("__debug__/", include(debug_toolbar.urls)),
	] + urlpatterns + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
