// Theme of the library pages (SPEC-0025): light or dark, nothing else. Loaded first and not deferred, so the theme is set
// before the first paint. The choice is kept in this browser (localStorage, library origin only); without one, the system's.
(function () {
  var theme;
  try {
    theme = localStorage.getItem("library-theme");
  } catch (error) {
    theme = null;
  }
  if (theme !== "light" && theme !== "dark") {
    theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", theme);
})();
