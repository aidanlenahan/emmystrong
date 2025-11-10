// js/script.js
// Loads partials/navbar.html into <div id="navbar"></div> and initializes nav behavior.
// Designed to work on GitHub Pages (same-origin fetch).
// Includes fallback if fetch fails.

document.addEventListener("DOMContentLoaded", () => {
  const navbarContainer = document.getElementById("navbar");
  const partialPath = "partials/navbar.html";

  function initNavBehavior() {
    // Dropdown open/close
    document.querySelectorAll(".nav-dropdown").forEach(drop => {
      const btn = drop.querySelector(".dropdown-toggle");
      const menu = drop.querySelector(".dropdown-menu");

      // hover opens on desktop via CSS, but add click toggle for accessibility/mobile
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const expanded = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!expanded));
        menu.classList.toggle("open");
      });
    });

    // Close any open dropdown if clicking outside
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".nav-dropdown")) {
        document.querySelectorAll(".dropdown-menu.open").forEach(m => m.classList.remove("open"));
        document.querySelectorAll(".dropdown-toggle[aria-expanded='true']").forEach(b => b.setAttribute("aria-expanded", "false"));
      }
    });

    // Mobile toggle
    const mobileToggle = document.getElementById("mobile-toggle");
    const navList = document.querySelector(".nav-list");
    if (mobileToggle && navList) {
      mobileToggle.addEventListener("click", () => {
        const expanded = mobileToggle.getAttribute("aria-expanded") === "true";
        mobileToggle.setAttribute("aria-expanded", String(!expanded));
        navList.classList.toggle("open");
      });
    }
  }

  function insertFallbackNav() {
    navbarContainer.innerHTML = `
      <nav class="site-nav">
        <div class="nav-inner">
          <a class="brand" href="index.html">EmmyStrong</a>
          <ul class="nav-list open">
            <li><a href="index.html">Home</a></li>
            <li><a href="about.html">About</a></li>
            <li><a href="donate.html">Donate</a></li>
            <li><a href="news.html">News</a></li>
          </ul>
        </div>
      </nav>
    `;
    // No JS needed for fallback beyond basic display.
  }

  if (!navbarContainer) {
    console.error("Navbar container (#navbar) not found in DOM.");
    return;
  }

  // Try to fetch partial (works on GitHub Pages)
  fetch(partialPath).then(resp => {
    if (!resp.ok) throw new Error("Network response was not ok");
    return resp.text();
  }).then(html => {
    navbarContainer.innerHTML = html;
    // Wait a tick then initialize behavior
    setTimeout(initNavBehavior, 20);
  }).catch(err => {
    console.warn("Loading navbar partial failed:", err);
    insertFallbackNav();
  });
});
