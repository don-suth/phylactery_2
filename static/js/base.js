const searchModal = document.getElementById("searchModal");
const searchInput = document.getElementById("searchInput");

searchModal.addEventListener("shown.bs.modal", () => {
	searchInput.focus();
})
