// js/script.js

// Site root, worked out from this script's own URL (/js/script.js -> /), so
// partials load correctly from any page, including the 404 page at deep paths.
const SITE_ROOT = new URL("../", document.currentScript.src);

// --- Clean URLs: /about.html -> /about, /index.html -> / (GitHub Pages serves both) ---
(function stripHtmlExtension() {
  const path = window.location.pathname;
  if (/\.html$/.test(path) && !/\/404\.html$/.test(path)) {
    const clean = path.replace(/(^|\/)index\.html$/, "$1").replace(/\.html$/, "");
    window.history.replaceState(null, "", clean + window.location.search + window.location.hash);
  }
})();

function normalizePath(p) {
  p = p.replace(/\.html$/, "").replace(/\/index$/, "/");
  if (p.length > 1) p = p.replace(/\/$/, "");
  return p || "/";
}

document.addEventListener("DOMContentLoaded", () => {
  const navbarContainer = document.getElementById("navbar");

  function initNavBehavior() {
    const navList = document.querySelector(".nav-list");
    const navItems = Array.from(navList.querySelectorAll(":scope > li"));
    const mobileToggle = document.querySelector(".mobile-toggle");

    if (mobileToggle) {
      mobileToggle.addEventListener("click", () => {
        const expanded = navList.classList.toggle("open");
        mobileToggle.setAttribute("aria-expanded", String(expanded));
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && navList.classList.contains("open")) {
          navList.classList.remove("open");
          mobileToggle.setAttribute("aria-expanded", "false");
          mobileToggle.focus();
        }
      });
    }

    // Collapse overflowing items into a "More" menu on narrow desktop widths
    function adjustNavItems() {
      const navInner = document.querySelector(".nav-inner");
      const brand = document.querySelector(".brand");
      const toggleWidth = mobileToggle ? mobileToggle.offsetWidth : 0;
      const availableWidth = navInner.offsetWidth - brand.offsetWidth - toggleWidth - 50;

      navItems.forEach(item => item.style.display = "");
      const existing = navList.querySelector(".nav-dropdown");
      if (existing) existing.remove();

      if (window.innerWidth <= 800) return;

      let currentWidth = 0;
      const hiddenItems = [];
      navItems.forEach(item => {
        currentWidth += item.offsetWidth;
        if (currentWidth >= availableWidth) hiddenItems.push(item);
      });

      if (hiddenItems.length > 0) {
        const moreDropdown = document.createElement("li");
        moreDropdown.className = "nav-dropdown";
        moreDropdown.innerHTML = `
          <button class="dropdown-toggle" type="button" aria-haspopup="true">More</button>
          <ul class="dropdown-menu"></ul>
        `;
        const dropdownMenu = moreDropdown.querySelector(".dropdown-menu");
        hiddenItems.forEach(item => {
          dropdownMenu.appendChild(item.cloneNode(true));
          item.style.display = "none";
        });
        navList.appendChild(moreDropdown);
      }
    }

    adjustNavItems();
    window.addEventListener("resize", adjustNavItems);
  }

  function insertFallbackNav() {
    navbarContainer.innerHTML = `
      <nav class="site-nav" aria-label="Main">
        <div class="nav-inner">
          <a class="brand" href="/">EmmyStrong</a>
          <ul class="nav-list open">
            <li><a href="/">Home</a></li>
            <li><a href="/about">About</a></li>
            <li><a href="/donate">Donate</a></li>
            <li><a href="/contact">Contact</a></li>
          </ul>
        </div>
      </nav>
    `;
  }

  function highlightActiveLink() {
    const current = normalizePath(window.location.pathname);
    document.querySelectorAll(".nav-list a").forEach(link => {
      if (normalizePath(new URL(link.href).pathname) === current) {
        link.setAttribute("aria-current", "page");
        link.parentElement.classList.add("active");
      }
    });
  }

  // Open links to other websites in a new tab (internal links and mailto stay put)
  function openExternalLinksInNewTab() {
    document.querySelectorAll("a[href^='http']").forEach(link => {
      if (link.hostname === window.location.hostname) return;
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener");
    });
  }

  function initializeSiteBehaviors() {
    initNavBehavior();
    highlightActiveLink();
    openExternalLinksInNewTab();
  }

  if (!navbarContainer) {
    console.error("Navbar container (#navbar) not found in DOM.");
    return;
  }

  fetch(new URL("partials/navbar.html", SITE_ROOT))
    .then(resp => {
      if (!resp.ok) throw new Error("Network response was not ok");
      return resp.text();
    })
    .then(html => { navbarContainer.innerHTML = html; })
    .catch(err => {
      console.warn("Loading navbar partial failed:", err);
      insertFallbackNav();
    })
    .finally(() => setTimeout(initializeSiteBehaviors, 20));

  const footerContainer = document.getElementById("footer");
  if (footerContainer) {
    fetch(new URL("partials/footer.html", SITE_ROOT))
      .then(resp => {
        if (!resp.ok) throw new Error("Network response was not ok");
        return resp.text();
      })
      .then(html => {
        footerContainer.innerHTML = html;
        openExternalLinksInNewTab();
      })
      .catch(err => {
        console.warn("Loading footer partial failed:", err);
        footerContainer.innerHTML = `
          <footer class="site-footer">
            <div class="container">
              <p>© 2026 EmmyStrong Foundation, a 501(c)(3) charitable organization.</p>
            </div>
          </footer>
        `;
      });
  }
});
