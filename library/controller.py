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
	def member_has_borrowing_permissions(self, member: Member) -> bool:
		"""
		Determines whether a Member can borrow Items.
		All the following conditions need to be True:
			- The Member needs to be a valid member
			- The Member needs to have no Library sanctions on them (from strikes).
			- TODO: When Library Strikes get implemented, add them in here.
		"""
		return (
			member.is_valid_member()
		)
	
	def get_item_availability_info(self, item: Item) -> dict:
		"""
		Given an Item, determines the following:
			- The maximum due date for this item, if it was to be borrowed today
			- Whether the item is available to borrow
			- Whether the item is in the clubroom
			- If not available, gives an expected date for return.
		"""
		pass
	
	
	def item_max_due_date(self, item: Item) -> date:
		"""
		Returns the maximum due date for an Item.
		"""
		pass


def get_library_controller() -> LibraryController:
	return LibraryController()

