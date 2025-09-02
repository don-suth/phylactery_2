from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import UnigamesUser

def gatekeeper_required(function=None):
	"""
	Decorator for views - requires a Gatekeeper to be logged in.
	If they are logged in, but not a Gatekeeper, then raise 403.
	Otherwise, redirect them to the login page.
	"""
	
	def gatekeeper_test(u):
		if u.is_authenticated:
			if u.get_member is not None and u.get_member.is_gatekeeper():
				return True
			else:
				raise PermissionDenied
		else:
			return False
		
	actual_decorator = user_passes_test(gatekeeper_test)
	
	if function:
		return actual_decorator(function)
	return actual_decorator


def committee_required(function=None):
	"""
	Decorator for views - requires a Committee Member to be logged in.
	If they are logged in, but not Committee, then raise 403.
	Otherwise, redirect them to the login page.
	"""
	
	def committee_test(u):
		if u.is_authenticated:
			if u.get_member is not None and u.get_member.is_committee():
				return True
			else:
				raise PermissionDenied
		else:
			return False
	
	actual_decorator = user_passes_test(committee_test)
	
	if function:
		return actual_decorator(function)
	return actual_decorator


def exec_required(function=None):
	"""
	Decorator for views - requires an Executive Committee Member to be logged in.
	(Being either President, VP, Treasurer, Secretary, or Librarian)
	If they are logged in, but not Exec, then raise 403.
	Otherwise, redirect them to the login page.
	"""
	
	def exec_test(u):
		if u.is_authenticated:
			if u.get_member is not None and u.get_member.is_exec():
				return True
			else:
				raise PermissionDenied
		else:
			return False
	
	actual_decorator = user_passes_test(exec_test)
	
	if function:
		return actual_decorator(function)
	return actual_decorator


def staff_required(function=None):
	"""
	Decorator for views - requires the User to be staff (can access the admin)
	and to have a linked Unigames member.
	"""
	
	def is_member_test(u: UnigamesUser):
		if u.is_authenticated:
			if u.get_member is not None and u.is_staff:
				return True
			else:
				raise PermissionDenied
		else:
			return False
	
	actual_decorator = user_passes_test(is_member_test)
	
	if function:
		return actual_decorator(function)
	return actual_decorator


def potential_superuser_required(function=None):
	"""
	Decorator for views - requires a potential superuser to be logged in.
	Currently, this is Webkeepers. But this could be expanded to exec as well.
	If they are logged in, but not a Webkeeper, then raise 403.
	Otherwise, redirect them to the login page.
	"""
	
	def webkeeper_test(u):
		if u.is_authenticated:
			if u.get_member is not None and u.get_member.is_webkeeper():
				return True
			else:
				raise PermissionDenied
		else:
			return False
	
	actual_decorator = user_passes_test(webkeeper_test)
	
	if function:
		return actual_decorator(function)
	return actual_decorator


def superuser_required(function=None):
	"""
	Decorator for views - requires a superuser to be logged in.
	If they are logged in, but not a superuser, then raise 403.
	Otherwise, redirect them to the login page.
	"""
	
	def superuser_test(u):
		if u.is_authenticated:
			if u.get_member is not None and u.get_member.is_superuser():
				return True
			else:
				raise PermissionDenied
		else:
			return False
	
	actual_decorator = user_passes_test(superuser_test)
	
	if function:
		return actual_decorator(function)
	return actual_decorator
