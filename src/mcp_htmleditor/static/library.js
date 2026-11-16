/* Web library pages (SPEC-0025, DEC-009, DEC-031). Loaded by every page with defer.
   Dates: each <time datetime="<UTC ISO>"> is rewritten in the browser's own time zone as "D Mon YYYY HH:MM"
   (24 hour clock, day without leading zero, English month abbreviations, seconds dropped); the server only sends
   the UTC text as the fallback without JavaScript. Back after Sign out: a page restored from the back/forward cache
   is reloaded, so the server decides again and a signed out browser gets the sign in page.
   Administration (US-0130): the Create folder form is sent with fetch as JSON (the server refuses any other content
   type); success reloads the page, a refusal is written with textContent into the alert next to the field (the
   JSON "error", else the alert's own text for a page answer: data-denied for 403, data-unavailable otherwise).
   Delete folder (US-0131): each row's button opens the one <dialog> (modal, focus in its field); Cancel or Escape
   closes it without a request and focus returns to that button; Delete folder sends {"confirm": typed text} for the
   button's folder id, reloads on success, writes a refusal into the dialog's alert as above.
   Members (US-0132): per folder, Add member sends {"email", "role"} to /api/folders/<id>/members, a member's role
   chooser sends the same on change, Remove sends {"email"} to .../members/remove; each reloads on success and writes
   a refusal into the alert of that folder's Members section. */
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

  function sendJson(path, payload, alert) {
    fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
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

  function createFolder(event) {
    event.preventDefault();
    sendJson("/api/folders", {name: document.getElementById("folder-name").value},
      document.getElementById("create-folder-alert"));
  }

  function bindFolderDeletion() {
    var dialog = document.getElementById("delete-folder");
    var field = document.getElementById("delete-folder-name");
    var alert = document.getElementById("delete-folder-alert");
    var opener = null;
    if (!dialog) {
      return;
    }
    document.querySelectorAll("button.delete-folder").forEach(function (button) {
      button.addEventListener("click", function () {
        opener = button;
        field.value = "";
        alert.textContent = "";
        alert.hidden = true;
        dialog.showModal();
        field.focus();
      });
    });
    document.getElementById("delete-folder-cancel").addEventListener("click", function () {
      dialog.close();
    });
    dialog.addEventListener("close", function () {
      if (opener) {
        opener.focus();
      }
    });
    document.getElementById("delete-folder-form").addEventListener("submit", function (event) {
      event.preventDefault();
      sendJson("/api/folders/" + opener.dataset.folderId + "/delete", {confirm: field.value}, alert);
    });
  }

  function membersPath(control) {
    return "/api/folders/" + control.dataset.folderId + "/members";
  }

  function membersAlert(control) {
    return control.closest("section.members").querySelector("p[role=alert]");
  }

  function bindMembers() {
    document.querySelectorAll("form.add-member").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        sendJson(membersPath(form), {email: form.elements.email.value, role: form.elements.role.value},
          membersAlert(form));
      });
    });
    document.querySelectorAll("select.member-role").forEach(function (chooser) {
      chooser.addEventListener("change", function () {
        sendJson(membersPath(chooser), {email: chooser.dataset.email, role: chooser.value}, membersAlert(chooser));
      });
    });
    document.querySelectorAll("button.remove-member").forEach(function (button) {
      button.addEventListener("click", function () {
        sendJson(membersPath(button) + "/remove", {email: button.dataset.email}, membersAlert(button));
      });
    });
  }

  function bindAdministration() {
    var form = document.getElementById("create-folder");
    if (form) {
      form.addEventListener("submit", createFolder);
    }
    bindFolderDeletion();
    bindMembers();
  }

  document.addEventListener("DOMContentLoaded", localizeTimes);
  document.addEventListener("DOMContentLoaded", bindAdministration);
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });
})();
