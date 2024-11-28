from datetime import date
from library.models import Item, Reservation, BorrowerDetails, BorrowRecord
from members.models import Member


class LibraryController:
	"""
	This controller will be the centralised class that handles:
		- Determining whether an item can be borrowed
		- Determining who can borrow it
		- Actually performing the borrow / returning
		- Notifications for those events
		- Notifications for overdue items
	"""
	def member_can_borrow_items(self, member: Member) -> bool:
		"""
		Controls whether a Member can borrow Items.
		All the following conditions need to be True:
			- The Member needs to be a valid member
			- The Member needs to have no Library sanctions on them (from strikes).
			- TODO: When Library Strikes get implemented, add them in here.
		"""
		return (
			member.is_valid_member()
		)
	
	def item_max_due_date(self, item: Item) -> date:
		"""
		Returns the maximum due date for an Item.
		"""
		pass


def get_library_controller() -> LibraryController:
	return LibraryController()

