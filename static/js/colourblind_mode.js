(() => {
	'use strict'

	const getStoredColourBlindTheme = () => localStorage.getItem('colour_blind_theme')
	const setStoredColourBlindTheme = cb_theme => localStorage.setItem('colour_blind_theme', cb_theme)

	const getPreferredColourBlindTheme = () => {
		const storedColourBlindTheme = getStoredColourBlindTheme()
		if (storedColourBlindTheme) {
			return storedColourBlindTheme
		}

		return 'off'
	}

	const setColourBlindTheme = cb_theme => {
		document.documentElement.setAttribute('data-cb-theme', cb_theme)
	}

	setColourBlindTheme(getPreferredColourBlindTheme())

	const showActiveColourBlindTheme = (cb_theme) => {
		document.querySelectorAll(".cb-label").forEach(element => {
			element.textContent = cb_theme
		})
		document.querySelectorAll("[data-cb-theme-value]").forEach(element => {
			element.classList.remove("active")
			element.setAttribute("aria-pressed", "false")
		})
		const btnToActive = document.querySelector(`[data-cb-theme-value="${cb_theme}"]`)
		btnToActive.classList.add("active")
		btnToActive.setAttribute("aria-pressed", "true")
	}

	window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
		const storedColourBlindTheme = getStoredColourBlindTheme()
		if (storedColourBlindTheme === null || storedColourBlindTheme === "auto") {
			setColourBlindTheme(getPreferredColourBlindTheme())
		}
	})

	window.addEventListener("DOMContentLoaded", () => {
		showActiveColourBlindTheme(getPreferredColourBlindTheme())

		document.querySelectorAll("[data-cb-theme-value]").forEach(element => {
			element.addEventListener("click", () => {
				const cb_theme = element.getAttribute("data-cb-theme-value")
				setStoredColourBlindTheme(cb_theme)
				setColourBlindTheme(cb_theme)
				showActiveColourBlindTheme(cb_theme)
			})
		})
	})
})()