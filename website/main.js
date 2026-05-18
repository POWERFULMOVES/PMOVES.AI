// PMOVES.AI landing page — progressive enhancement.
// No framework, no dependencies. Runs after defer.
(function () {
  "use strict";

  // --- Footer year -------------------------------------------------
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  // --- Mobile nav drawer -------------------------------------------
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  var body = document.body;

  function closeNav() {
    body.classList.remove("nav-open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }
  function openNav() {
    body.classList.add("nav-open");
    if (toggle) toggle.setAttribute("aria-expanded", "true");
  }

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      if (body.classList.contains("nav-open")) closeNav();
      else openNav();
    });

    // Close drawer on anchor click
    nav.addEventListener("click", function (e) {
      var t = e.target;
      if (t && t.tagName === "A") closeNav();
    });

    // Close drawer on Escape
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && body.classList.contains("nav-open")) {
        closeNav();
        if (toggle) toggle.focus();
      }
    });

    // Re-sync on resize up to desktop
    var mql = window.matchMedia("(min-width: 860px)");
    var onChange = function () { if (mql.matches) closeNav(); };
    if (mql.addEventListener) mql.addEventListener("change", onChange);
    else if (mql.addListener) mql.addListener(onChange);
  }

  // --- Smooth scroll for in-page anchors, respecting reduced-motion
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce) {
    document.querySelectorAll('a[href^="#"]').forEach(function (a) {
      a.addEventListener("click", function (e) {
        var id = a.getAttribute("href");
        if (!id || id === "#" || id.length < 2) return;
        var target = document.querySelector(id);
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        // Move focus for accessibility (without re-scrolling)
        if (target.hasAttribute("tabindex") === false) {
          target.setAttribute("tabindex", "-1");
        }
        target.focus({ preventScroll: true });
      });
    });
  }

  // --- Lazy-load hint for any future <img data-src> assets ---------
  // Founder: drop <img data-src="/assets/foo.jpg" alt="..."> in markup
  // and this block will hydrate them when they enter the viewport.
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var img = entry.target;
        var src = img.getAttribute("data-src");
        if (src) {
          img.setAttribute("src", src);
          img.removeAttribute("data-src");
        }
        io.unobserve(img);
      });
    }, { rootMargin: "200px 0px" });
    document.querySelectorAll("img[data-src]").forEach(function (img) {
      io.observe(img);
    });
  }

  // TODO(founder): wire Cloudflare Web Analytics here if you want a
  // pure first-party beacon. No third-party trackers ship by default.
})();
