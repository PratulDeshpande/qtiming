/* qtiming docs: search (MkDocs search worker), contents highlight, copy buttons, margin notes,
   table scroll wrappers, narrow-screen placement. No dependencies. */
(function () {
  "use strict";
  var base = (window.QT && window.QT.base) || ".";
  var wide = window.matchMedia("(min-width: 1181px)");
  function join(a, b) { return a.replace(/\/$/, "") + "/" + b.replace(/^\//, ""); }
  function el(tag, text) { var n = document.createElement(tag); if (text) { n.textContent = text; } return n; }

  /* search: the plugin's worker takes {init} and {query}, replies {allowSearch} and {results} */
  var input = document.getElementById("qt-q"), box = document.getElementById("qt-results");
  if (input && box && window.Worker) {
    var worker, ready = false, minLen = 2, active = -1;
    try { worker = new Worker(join(base, "search/worker.js")); } catch (e) { worker = null; }
    if (worker) {
      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      box.id = "qt-results";
      var show = function (rs) {
        active = -1; input.removeAttribute("aria-activedescendant");
        box.hidden = false; input.setAttribute("aria-expanded", "true");
        box.textContent = "";
        if (!rs.length) { box.appendChild(el("p", "No results.")); return; }
        rs.slice(0, 8).forEach(function (r, i) {
          var a = el("a"); a.id = "qt-r" + i; a.setAttribute("role", "option"); a.href = join(base, r.location);
          a.appendChild(el("b", r.title)); a.appendChild(el("span", (r.summary || "").slice(0, 150)));
          box.appendChild(a);
        });
      };
      var close = function () { box.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); };
      worker.postMessage({ init: true });
      worker.onmessage = function (e) {
        if (e.data.config) { minLen = Math.max(1, e.data.config.min_search_length || 2); }
        else if (e.data.allowSearch) { ready = true; }
        else if (e.data.results) { show(e.data.results); }
      };
      input.addEventListener("input", function () {
        var q = input.value.trim();
        if (q.length < minLen || !ready) { close(); return; }
        worker.postMessage({ query: q });
      });
      input.addEventListener("keydown", function (e) {
        var items = box.querySelectorAll("a");
        if (e.key === "Escape") { close(); input.blur(); }
        else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && items.length) {
          e.preventDefault();
          active = (active + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
          items.forEach(function (a, i) { a.setAttribute("aria-selected", i === active ? "true" : "false"); });
          input.setAttribute("aria-activedescendant", items[active].id);
          items[active].scrollIntoView({ block: "nearest" });
        } else if (e.key === "Enter" && active >= 0) { e.preventDefault(); items[active].click(); }
      });
      document.addEventListener("click", function (e) { if (!e.target.closest(".search")) { close(); } });
      document.addEventListener("keydown", function (e) {
        var t = e.target.tagName;
        if (e.key === "/" && t !== "INPUT" && t !== "TEXTAREA") { e.preventDefault(); input.focus(); }
      });
    }
  } else if (input) { input.disabled = true; input.placeholder = "Search needs JavaScript"; }

  /* contents: mark the heading currently in view */
  var links = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  if (links.length && "IntersectionObserver" in window) {
    var map = {};
    links.forEach(function (a) { map[decodeURIComponent(a.hash.slice(1))] = a; });
    var heads = Object.keys(map).map(function (id) { return document.getElementById(id); }).filter(Boolean);
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting) { links.forEach(function (l) { l.classList.remove("on"); }); map[en.target.id].classList.add("on"); }
      });
    }, { rootMargin: "-72px 0px -70% 0px" });
    heads.forEach(function (h) { io.observe(h); });
  }

  var prose = document.querySelector(".prose");

  /* tables: scroll inside a wrapper so the page never scrolls sideways */
  document.querySelectorAll(".prose > table").forEach(function (t) {
    var w = el("div"); w.className = "tw"; w.tabIndex = 0; w.setAttribute("role", "region");
    w.setAttribute("aria-label", "Table, scrolls sideways");
    t.parentNode.insertBefore(w, t); w.appendChild(t);
  });

  /* scrollable code blocks must be reachable by keyboard */
  var pres = document.querySelectorAll(".prose pre");
  function focusScrollers() {
    pres.forEach(function (p) {
      if (p.scrollWidth > p.clientWidth) { p.tabIndex = 0; p.setAttribute("role", "region"); p.setAttribute("aria-label", "Code, scrolls sideways"); }
      else { p.removeAttribute("tabindex"); p.removeAttribute("role"); p.removeAttribute("aria-label"); }
    });
  }
  focusScrollers(); window.addEventListener("resize", focusScrollers);

  /* copy buttons on code blocks */
  if (navigator.clipboard) {
    document.querySelectorAll(".prose pre").forEach(function (pre) {
      var b = el("button", "Copy");
      b.type = "button"; b.className = "copy"; b.setAttribute("aria-label", "Copy code");
      b.addEventListener("click", function () {
        var code = pre.querySelector("code");
        navigator.clipboard.writeText((code || pre).innerText).then(function () {
          b.textContent = "Copied"; setTimeout(function () { b.textContent = "Copy"; }, 1600);
        });
      });
      pre.appendChild(b);
    });
  }

  /* margin notes: on wide screens the footnotes move beside the text, under the contents */
  var foot = document.querySelector(".prose .footnote"), margin = document.querySelector(".margin");
  if (foot && margin && wide.matches) {
    var list = foot.querySelector("ol");
    if (list) {
      var notes = el("div"); notes.className = "notes";
      notes.appendChild(el("h2", "Notes"));
      var ol = list.cloneNode(true);
      ol.querySelectorAll(".footnote-backref").forEach(function (a) { a.remove(); });
      ol.querySelectorAll("[id]").forEach(function (n) { n.removeAttribute("id"); });
      notes.appendChild(ol); margin.appendChild(notes);
      document.documentElement.classList.add("has-notes");
    }
  }

  /* narrow screens: the margin is hidden, so the figure and the page contents move into the text */
  if (!wide.matches && prose) {
    var first = prose.querySelector(":scope > p");
    var anchor = prose.querySelector(":scope > pre") || first;
    var fig = document.querySelector(".margin .fig");
    if (fig && first) {
      var c = fig.cloneNode(true); c.classList.add("fig-inline");
      c.querySelectorAll("[id]").forEach(function (n) { n.removeAttribute("id"); });
      var svg = c.querySelector("svg");
      if (svg) { svg.removeAttribute("aria-labelledby"); svg.setAttribute("aria-label", "Feedforward timing window, 0 to 600 ns"); }
      anchor.parentNode.insertBefore(c, anchor.nextSibling);
    }
    var mt = prose.querySelector(".mtoc");
    if (mt && first) { first.parentNode.insertBefore(mt, first.nextSibling); }
  }
})();
