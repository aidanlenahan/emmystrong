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
  } else {
    console.error("Navbar container (#navbar) not found.");
  }
});
