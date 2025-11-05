// Main theme JS: dropdown toggling + mobile toggle
// Expose initNavbar so navbar loader can call it after injecting HTML.
window.initNavbar = function() {
  // Dropdown toggle (click to open/close)
  document.querySelectorAll(".dropdown-toggle").forEach(toggle => {
    const parent = toggle.closest(".dropdown");
    toggle.addEventListener("click", (e) => {
      e.preventDefault();
      // close other dropdowns
      document.querySelectorAll(".dropdown").forEach(d => {
        if (d !== parent) d.classList.remove("active");
      });
      parent.classList.toggle("active");
    });
  });

  // Close dropdowns when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".dropdown")) {
      document.querySelectorAll(".dropdown").forEach(d => d.classList.remove("active"));
    }
  });

  // Mobile menu (if you include a mobile button; safe no-op if not present)
  const mobileBtn = document.getElementById("mobile-menu");
  const navLinks = document.querySelector(".nav-links");
  if (mobileBtn && navLinks) {
    mobileBtn.addEventListener("click", () => {
      navLinks.classList.toggle("active");
    });
  }
};

// If navbar HTML is already present (e.g., preview where fetch succeeded earlier),
// initialize immediately.
document.addEventListener("DOMContentLoaded", () => {
  if (document.querySelector(".nav-links")) window.initNavbar();
});
