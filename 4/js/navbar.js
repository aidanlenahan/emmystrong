// js/navbar.js
document.addEventListener("DOMContentLoaded", async () => {
  const container = document.getElementById("navbar-container");
  if (!container) return;

  const path = "partials/navbar.html";

  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const html = await res.text();
    container.innerHTML = html;
    initNavbar();
  } catch (err) {
    console.error("Failed to load navbar:", err);
    container.innerHTML = fallbackNavbar();
    initNavbar();
  }
});

function initNavbar() {
  // Mobile toggle
  const toggle = document.querySelector(".mobile-toggle");
  const navList = document.querySelector(".nav-list");
  if (toggle && navList) {
    toggle.addEventListener("click", () => {
      navList.classList.toggle("open");
    });
  }

  // Dropdown toggle (mobile)
  document.querySelectorAll(".dropdown-toggle").forEach(btn => {
    btn.addEventListener("click", e => {
      e.preventDefault();
      const menu = btn.nextElementSibling;
      if (menu) menu.style.display = menu.style.display === "block" ? "none" : "block";
    });
  });
}

function fallbackNavbar() {
  return `
    <nav class="site-nav">
      <div class="nav-inner">
        <a href="index.html" class="brand">EmmyStrong</a>
        <button class="mobile-toggle"><span></span><span></span><span></span></button>
        <ul class="nav-list">
          <li><a href="index.html">Home</a></li>
          <li><a href="about.html">About</a></li>
          <li><a href="donate.html">Donate</a></li>
          <li><a href="news.html">News</a></li>
          <li><a href="events.html">Events</a></li>
          <li><a href="resources.html">Resources</a></li>
          <li><a href="contact.html">Contact</a></li>
        </ul>
      </div>
    </nav>
  `;
}
