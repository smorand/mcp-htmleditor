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
   a refusal into the alert of that folder's Members section.
   Upload (US-0141): choosing a file in the Upload field sends its bytes with XMLHttpRequest to
   /api/folders/<id>/presentations (X-File-Name is the percent encoded name); the answer's message or error is written
   with textContent into the status area, and on success the list of the page is replaced by the server's.
   US-0143: while the file is sent the status reads "<file name> <percent>%" (progressText: a whole number rounded down,
   at most 99); the extension and the 25 MB are checked before anything is sent; a second choice made while one upload
   is in progress is ignored; an error or an abort reads the page's own failure text.
   US-0144: a 409 with the existing name opens the Replace / Cancel question; Replace sends the file again with X-Replace.
   Design (app-design): the theme button toggles light and dark; a cover that answers 404 is hidden.
   US-0145: a row's Delete opens the same dialog as Delete / Cancel; Delete sends DELETE /api/presentations/<id>, then the list
   is replaced by the server's (a refusal reads the page's own Access denied. text). */
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

  function uploadAnswer(request, status) {
    try {
      var answer = JSON.parse(request.responseText);
      return answer.message || answer.error || (answer.collision ? answer.collision : status.dataset.failed);
    } catch (error) {
      return request.status === 403 ? status.dataset.denied : status.dataset.failed;
    }
  }

  function refreshListing() {
    fetch(window.location.href, {credentials: "same-origin"}).then(function (response) {
      return response.ok ? response.text() : "";
    }).then(function (text) {
      var next = new DOMParser().parseFromString(text, "text/html").querySelector("ul.presentations, .card.empty");
      var current = document.querySelector("ul.presentations, .card.empty");
      if (next && current) {
        current.replaceWith(next);
        localizeTimes();
      }
    });
  }

  var MAX_UPLOAD_BYTES = 26214400;
  var uploading = false;

  /* "<file name> <percent>%", the percent a whole number rounded down and never above 99: the 100 is the answer. */
  function progressText(name, loaded, total) {
    var percent = total > 0 ? Math.min(99, Math.floor(100 * loaded / total)) : 0;
    return name + " " + percent + "%";
  }
  window.progressText = progressText;

  function finishUpload(input, status, text) {
    status.textContent = text;
    input.value = "";
    uploading = false;
  }

  /* One question dialog for two questions: a name collision (Replace / Cancel, DEC-035) and a deletion (Delete /
     Cancel). The name goes into the question with textContent; Cancel changes nothing and focus goes back. */
  function ask(kind, name, onYes, back) {
    var dialog = document.getElementById("confirm-dialog");
    var question = document.getElementById("confirm-question");
    var yes = document.getElementById("confirm-yes");
    question.textContent = question.dataset[kind].replace("{name}", name);
    yes.textContent = yes.dataset[kind];
    yes.disabled = false;
    yes.onclick = function () {
      if (yes.disabled) {
        return;
      }
      yes.disabled = true;  /* the dialog stays until the request ends: a second click has no card under it */
      onYes(function () {
        yes.disabled = false;
        dialog.close();
      });
    };
    document.getElementById("confirm-no").onclick = function () {
      dialog.close();
    };
    dialog.onclose = function () {
      back.focus();
    };
    dialog.showModal();
  }

  function askReplace(file, existing, status, section, input) {
    status.textContent = "";
    input.value = "";
    ask("replace", existing, function (done) {
      sendFile(file, status, section, input, true, done);
    }, input);
  }

  function deletePresentation(button, status, done) {
    fetch("/api/presentations/" + button.dataset.presentationId, {method: "DELETE", credentials: "same-origin"})
      .then(function (response) {
        status.textContent = response.ok ? "" : status.dataset.denied;
        refreshListing();
        done();
      }, function () {
        status.textContent = status.dataset.failed;
        done();
      });
  }

  function bindDeletion() {
    var status = document.getElementById("upload-status");
    if (!status) {
      return;
    }
    document.addEventListener("click", function (event) {
      var button = event.target.closest("button.delete-presentation");
      if (button) {
        ask("delete", button.dataset.name, function (done) {
          deletePresentation(button, status, done);
        }, document.getElementById("upload-file"));
      }
    });
  }

  function sendFile(file, status, section, input, replace, done) {
    uploading = true;
    var request = new XMLHttpRequest();
    request.open("POST", "/api/folders/" + section.dataset.folderId + "/presentations");
    request.setRequestHeader("X-File-Name", encodeURIComponent(file.name));
    if (replace) {
      request.setRequestHeader("X-Replace", "1");
    }
    request.upload.onprogress = function (event) {
      status.textContent = progressText(file.name, event.loaded, event.lengthComputable ? event.total : file.size);
    };
    request.onload = function () {
      var collision = null;
      try {
        collision = request.status === 409 ? JSON.parse(request.responseText).collision : null;
      } catch (error) {
        collision = null;
      }
      uploading = false;
      if (done) {
        done();
      }
      if (collision !== null && collision !== undefined) {
        askReplace(file, collision, status, section, input);
        return;
      }
      finishUpload(input, status, uploadAnswer(request, status));
      if (request.status === 201) {
        refreshListing();
      }
    };
    request.onerror = request.onabort = function () {
      finishUpload(input, status, status.dataset.failed);
      if (done) {
        done();
      }
    };
    status.textContent = progressText(file.name, 0, file.size);
    request.send(file);
  }

  function sendUpload(input, status, section) {
    var file = input.files[0];
    if (uploading) {
      return;
    }
    if (!/\.html$/i.test(file.name)) {
      finishUpload(input, status, status.dataset.onlyHtml);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      finishUpload(input, status, status.dataset.tooLarge);
      return;
    }
    sendFile(file, status, section, input, false);
  }

  function bindUpload() {
    var section = document.getElementById("upload");
    var input = document.getElementById("upload-file");
    if (!section || !input) {
      return;
    }
    input.addEventListener("change", function () {
      if (input.files.length) {
        sendUpload(input, document.getElementById("upload-status"), section);
      }
    });
  }

  /* Theme (light or dark, kept in this browser; theme.js set it before the first paint). */
  function toggleTheme() {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("library-theme", next);
    } catch (error) {
      /* storage refused: the choice lasts for this page */
    }
  }

  /* A cover that does not exist (404) is hidden: the ridge of the card shows instead. An error event does not bubble,
     so it is caught on the way down; covers that failed before this script ran are found by their size. */
  function hideBrokenCover(img) {
    if (img.closest(".cover")) {
      img.hidden = true;
    }
  }

  function bindChrome() {
    document.addEventListener("click", function (event) {
      if (event.target.closest("[data-theme-toggle]")) {
        toggleTheme();
      }
    });
    document.addEventListener("error", function (event) {
      if (event.target.tagName === "IMG") {
        hideBrokenCover(event.target);
      }
    }, true);
    document.querySelectorAll(".cover img").forEach(function (img) {
      if (img.complete && img.naturalWidth === 0) {
        hideBrokenCover(img);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", localizeTimes);
  document.addEventListener("DOMContentLoaded", bindChrome);
  document.addEventListener("DOMContentLoaded", bindUpload);
  document.addEventListener("DOMContentLoaded", bindDeletion);
  document.addEventListener("DOMContentLoaded", bindAdministration);
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });
})();
