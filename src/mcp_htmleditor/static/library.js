/* Web library pages (SPEC-0025, DEC-009, DEC-031). Loaded by every page with defer.
   Dates: each <time datetime="<UTC ISO>"> is rewritten in the browser's own time zone as "D Mon YYYY HH:MM"
   (24 hour clock, day without leading zero, English month abbreviations, seconds dropped); the server only sends
   the UTC text as the fallback without JavaScript. Back after Sign out: a page restored from the back/forward cache
   is reloaded, so the server decides again and a signed out browser gets the sign in page. */
(function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function twoDigits(value) {
    return value < 10 ? "0" + value : String(value);
  }

  function formatDate(date) {
    return date.getDate() + " " + MONTHS[date.getMonth()] + " " + date.getFullYear() + " " +
      twoDigits(date.getHours()) + ":" + twoDigits(date.getMinutes());
  }

  function localizeTimes() {
    document.querySelectorAll("time[datetime]").forEach(function (element) {
      var date = new Date(element.getAttribute("datetime"));
      if (!isNaN(date.getTime())) {
        element.textContent = formatDate(date);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", localizeTimes);
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });
})();
