/* Keeps your place after an action (enrol, withdraw, move, plan changes).
   Just before an action form is sent, it remembers how far down the page you are and which
   cards are open; when the page comes back it puts you there again. */
(function () {
  var KEY = "enrolment-hub-view";

  function here() {
    return window.location.pathname + window.location.search;
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || !form.classList || !form.classList.contains("enrol-form")) {
      return;
    }
    var open = [];
    document.querySelectorAll("details[open][id]").forEach(function (el) {
      open.push(el.id);
    });
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ url: here(), y: window.scrollY, open: open }));
    } catch (error) {
      /* storage unavailable: the page simply reloads from the top */
    }
  });

  window.addEventListener("load", function () {
    var saved = null;
    try {
      saved = JSON.parse(sessionStorage.getItem(KEY) || "null");
      sessionStorage.removeItem(KEY);
    } catch (error) {
      return;
    }
    if (!saved || saved.url !== here()) {
      return;
    }
    (saved.open || []).forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.tagName === "DETAILS") {
        el.open = true;
      }
    });
    window.scrollTo(0, saved.y || 0);
  });
})();