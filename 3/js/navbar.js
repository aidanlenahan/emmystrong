// navbar.js — Theme 3 styled, compatible with GitHub Pages and file://
// Inserts the navbar dynamically into <div id="navbar"></div> in each HTML file

document.addEventListener("DOMContentLoaded", () => {
  const navbarHTML = `
    <nav class="navbar">
      <div class="navbar-container">
        <a href="index.html" class="nav-logo">Emmy Strong</a>
        <ul class="nav-links">
          <li><a href="index.html">Home</a></li>
          <li><a href="about.html">About</a></li>
          <li><a href="donate.html">Donate</a></li>
          <li><a href="news.html">News</a></li>
          <li class="dropdown">
            <a href="#" class="dropbtn">More</a>
            <div class="dropdown-content">
              <a href="resources.html">Resources</a>
              <a href="events.html">Events</a>
              <a href="contact.html">Contact</a>
            </div>
          </li>
        </ul>
      </div>
    </nav>
  `;

  const navbarContainer = document.getElementById("navbar");
  if (navbarContainer) {
    navbarContainer.innerHTML = navbarHTML;

    // Handle mobile dropdown click fallback
    const dropdownBtn = document.querySelector(".dropbtn");
    if (dropdownBtn) {
      dropdownBtn.addEventListener("click", (e) => {
        e.preventDefault();
        const dropdownContent = dropdownBtn.nextElementSibling;
        dropdownContent.classList.toggle("show");
      });
    }

    // Close dropdown when clicking outside
    window.addEventListener("click", (e) => {
      if (!e.target.matches(".dropbtn")) {
        const dropdowns = document.querySelectorAll(".dropdown-content");
        dropdowns.forEach((dd) => dd.classList.remove("show"));
      }
    });
  } else {
    console.error("Navbar container (#navbar) not found.");
  }
});
