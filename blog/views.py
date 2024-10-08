from django.http import Http404
from django.views.generic import ListView, DetailView

from .models import BlogPost


class AllBlogPostsView(ListView):
	"""
	View that shows a list of all BlogPosts.
	"""
	
	template_name = "blog/blog_list_view.html"
	context_object_name = "blogpost_list"
	model = BlogPost
	paginate_by = 10
	
	def get_queryset(self):
		"""
		Show only published posts by default,
		ordered by most recent.
		"""
		return BlogPost.objects.filter(
			published=True,
		).order_by("-publish_on")


class BlogPostDetailView(DetailView):
	"""
	View to show one specific BlogPost.
	Doesn't allow non-Committee members to see non-published posts.
	"""
	model = BlogPost
	template_name = "blog/blog_detail_view.html"
	slug_field = "slug_title"
	context_object_name = "post"
	
	def get_object(self, queryset=None):
		# If the post that's going to be viewed isn't published yet,
		# and if the requesting user isn't committee, then 404.
		blogpost = super().get_object(queryset=queryset)
		if not blogpost.is_published:
			if not (self.request.user.is_authenticated and self.request.user.member.is_committee()):
				# Raise 404 instead of Forbidden, to prevent data leakage
				raise Http404("No blog post found matching the query")
		return blogpost
