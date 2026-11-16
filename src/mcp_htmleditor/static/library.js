/* Web library pages (SPEC-0025, DEC-009, DEC-031). Loaded by every page with defer.
   Dates: each <time datetime="<UTC ISO>"> is rewritten in the browser's own time zone as "D Mon YYYY HH:MM"
   (24 hour clock, day without leading zero, English month abbreviations, seconds dropped); the server only sends
   the UTC text as the fallback without JavaScript. Back after Sign out: a page restored from the back/forward cache
   is reloaded, so the server decides again and a signed out browser gets the sign in page.
   Administration (US-0130): the Create folder form is sent with fetch as JSON (the server refuses any other content
   type); success reloads the page, a refusal is written with textContent into the alert next to the field (the
   JSON "error", else the alert's own text for a page answer: data-denied for 403, data-unavailable otherwise). */
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

  function showRefusal(alert, text) {
    alert.textContent = text;
    alert.hidden = false;
  }

  function refusalOf(alert, response) {
    return response.json().then(function (answer) {
      return answer.error;
    }, function () {
      return response.status === 403 ? alert.dataset.denied : alert.dataset.unavailable;
    });
  }

  function createFolder(event) {
    var alert = document.getElementById("create-folder-alert");
    event.preventDefault();
    fetch("/api/folders", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name: document.getElementById("folder-name").value})
    }).then(function (response) {
      if (response.ok) {
        window.location.reload();
        return;
      }
      return refusalOf(alert, response).then(function (text) {
        showRefusal(alert, text);
      });
    }, function () {
      showRefusal(alert, alert.dataset.unavailable);
    });
  }

  function bindAdministration() {
    var form = document.getElementById("create-folder");
    if (form) {
      form.addEventListener("submit", createFolder);
    }
  }

  document.addEventListener("DOMContentLoaded", localizeTimes);
  document.addEventListener("DOMContentLoaded", bindAdministration);
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });
})();
