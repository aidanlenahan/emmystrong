// js/script.js

document.addEventListener("DOMContentLoaded", () => {
  const navbarContainer = document.getElementById("navbar");
  const partialPath = "partials/navbar.html";

  function initNavBehavior() {
    const navList = document.querySelector(".nav-list");
    const navItems = Array.from(navList.querySelectorAll("li"));
    const mobileToggle = document.querySelector(".mobile-toggle");

    // --- Mobile Dropdown ---
    mobileToggle.addEventListener("click", () => {
      navList.classList.toggle("open");
      const expanded = navList.classList.contains("open");
      mobileToggle.setAttribute("aria-expanded", String(expanded));
    });

    // --- Dynamic "More" Dropdown for Desktop ---
    function adjustNavItems() {
      const navInner = document.querySelector(".nav-inner");
      const brand = document.querySelector(".brand");
      const availableWidth = navInner.offsetWidth - brand.offsetWidth - mobileToggle.offsetWidth - 50; // 50px buffer

      // Reset nav
      navItems.forEach(item => item.style.display = "list-item");
      if (document.querySelector(".nav-dropdown")) {
        document.querySelector(".nav-dropdown").remove();
      }

      if (window.innerWidth <= 800) {
        return; // Use mobile view
      }

      let currentWidth = 0;
      const visibleItems = [];
      const hiddenItems = [];

      navItems.forEach(item => {
        currentWidth += item.offsetWidth;
        if (currentWidth < availableWidth) {
          visibleItems.push(item);
        } else {
          hiddenItems.push(item);
        }
      });

      if (hiddenItems.length > 0) {
        const moreDropdown = document.createElement("li");
        moreDropdown.className = "nav-dropdown";
        moreDropdown.innerHTML = `
          <button class="dropdown-toggle">More</button>
          <ul class="dropdown-menu"></ul>
        `;
        const dropdownMenu = moreDropdown.querySelector(".dropdown-menu");

        hiddenItems.forEach(item => {
          dropdownMenu.appendChild(item.cloneNode(true));
          item.style.display = "none";
        });

        navList.appendChild(moreDropdown);

        moreDropdown.addEventListener("mouseenter", () => {
            dropdownMenu.style.display = "block";
        });
        moreDropdown.addEventListener("mouseleave", () => {
            dropdownMenu.style.display = "none";
        });
      }
    }

    // Initial check and on resize
    adjustNavItems();
    window.addEventListener("resize", adjustNavItems);
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
  }

  // --- Highlight Active Nav Link ---
  function highlightActiveLink() {
    const currentPage = window.location.pathname.split("/").pop() || "index.html";
    const navLinks = document.querySelectorAll(".nav-list a");

    navLinks.forEach(link => {
      const linkPage = link.getAttribute("href").split("/").pop();
      if (linkPage === currentPage) {
        link.parentElement.classList.add("active");
      }
    });
  }

  // --- Open External Links in New Tab ---
  function openExternalLinksInNewTab() {
    const links = document.querySelectorAll("a");
    links.forEach(link => {
        if (link.closest('.site-nav')) {
            return;
        }
        link.setAttribute("target", "_blank");
    });
  }

  // Initialize all behaviors after nav is loaded
  function initializeSiteBehaviors() {
    initNavBehavior();
    highlightActiveLink();
    openExternalLinksInNewTab();
  }

  if (!navbarContainer) {
    console.error("Navbar container (#navbar) not found in DOM.");
    return;
  }

  fetch(partialPath)
    .then(resp => {
      if (!resp.ok) throw new Error("Network response was not ok");
      return resp.text();
    })
    .then(html => {
      navbarContainer.innerHTML = html;
      setTimeout(initializeSiteBehaviors, 20); // Use the new initializer
    })
    .catch(err => {
      console.warn("Loading navbar partial failed:", err);
      insertFallbackNav();
      setTimeout(initializeSiteBehaviors, 20); // Also use for fallback
    });
});