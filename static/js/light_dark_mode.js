(() => {
	'use strict'

	const getStoredTheme = () => localStorage.getItem('theme')
	const setStoredTheme = theme => localStorage.setItem('theme', theme)

	const getPreferredTheme = () => {
		const storedTheme = getStoredTheme()
		if (storedTheme) {
			return storedTheme
		}

		return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
	}

	const setTheme = theme => {
		if (theme === 'auto') {
			document.documentElement.setAttribute('data-bs-theme', (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))

		} else {
			document.documentElement.setAttribute('data-bs-theme', theme)
		}
	}

	setTheme(getPreferredTheme())

	const showActiveTheme = (theme) => {
		document.querySelectorAll(".theme-label").forEach(element => {
			element.textContent = theme
		})
		document.querySelectorAll("[data-theme-value]").forEach(element => {
			element.classList.remove("active")
			element.setAttribute("aria-pressed", "false")
		})
		const btnToActive = document.querySelector(`[data-theme-value="${theme}"]`)
		btnToActive.classList.add("active")
		btnToActive.setAttribute("aria-pressed", "true")
	}

	window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
		const storedTheme = getStoredTheme()
		if (storedTheme === null || storedTheme === "auto") {
			setTheme(getPreferredTheme())
		}
	})

	window.addEventListener("DOMContentLoaded", () => {
		showActiveTheme(getPreferredTheme())

		document.querySelectorAll("[data-theme-value]").forEach(element => {
			element.addEventListener("click", () => {
				const theme = element.getAttribute("data-theme-value")
				setStoredTheme(theme)
				setTheme(theme)
				showActiveTheme(theme)
			})
		})
	})
})()