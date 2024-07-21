from library.models import Item, Reservation, BorrowerDetails, BorrowRecord


class LibraryController:
	"""
	This controller will be the centralised class that handles:
		- Determining whether an item can be borrowed
		- Determining who can borrow it
		- Actually performing the borrow / returning
		- Notifications for those events
		- Notifications for overdue items
	"""
	
	


library_controller = LibraryController()
