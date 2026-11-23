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

  // Events: hide ones that have ended since the page was last rebuilt, and on
  // phones collapse each event to its title and date until it's tapped.
  function initEvents() {
    const now = Date.now();
    document.querySelectorAll(".event-list-upcoming").forEach(list => {
      list.querySelectorAll(".event[data-end]").forEach(item => {
        if (Date.parse(item.dataset.end) <= now) item.remove();
      });
      if (!list.querySelector(".event")) {
        list.hidden = true;
        const empty = list.parentElement.querySelector(".events-empty");
        if (empty) empty.hidden = false;
      }
    });

    // Events: on phones each starts collapsed and only one stays open at a time;
    // on wider screens they're always open.
    const toggles = document.querySelectorAll(".event-toggle");
    if (!toggles.length) return;
    const phone = window.matchMedia("(max-width: 600px)");
    const apply = () => toggles.forEach(d => { d.open = !phone.matches; });
    apply();
    phone.addEventListener("change", apply);
    toggles.forEach(d => {
      d.querySelector("summary").addEventListener("click", e => {
        if (!phone.matches) e.preventDefault();
      });
      d.addEventListener("toggle", () => {
        if (!phone.matches || !d.open) return;
        toggles.forEach(other => { if (other !== d) other.open = false; });
      });
    });
  }

  // Slideshow for posts with more than one picture: swipe or scroll sideways,
  // or use the arrows and dots.
  function initCarousel(media) {
    const track = media.querySelector(".news-track");
    const slides = track.children;
    const button = (cls, label, text) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "news-nav " + cls;
      b.setAttribute("aria-label", label);
      b.textContent = text;
      media.appendChild(b);
      return b;
    };
    const prev = button("news-prev", "Previous picture", "‹");
    const next = button("news-next", "Next picture", "›");
    const dots = document.createElement("div");
    dots.className = "news-dots";
    const go = i => track.scrollTo({ left: i * track.clientWidth });
    Array.from(slides).forEach((_, i) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "news-dot";
      dot.setAttribute("aria-label", `Picture ${i + 1} of ${slides.length}`);
      dot.addEventListener("click", () => go(i));
      dots.appendChild(dot);
    });
    media.appendChild(dots);
    const current = () => Math.round(track.scrollLeft / (track.clientWidth || 1));
    const update = () => {
      const i = current();
      prev.disabled = i === 0;
      next.disabled = i === slides.length - 1;
      Array.from(dots.children).forEach((d, j) => d.setAttribute("aria-current", String(i === j)));
    };
    prev.addEventListener("click", () => go(current() - 1));
    next.addEventListener("click", () => go(current() + 1));
    track.addEventListener("scroll", update, { passive: true });
    update();
  }

  // News: each card shows the first few lines. If a post is longer, "Read more"
  // opens the whole post (picture, text, button) in a full-page view.
  function initNews() {
    const posts = document.querySelectorAll(".news-item");
    if (!posts.length) return;

    const modal = document.createElement("dialog");
    modal.className = "news-modal";
    modal.setAttribute("aria-label", "News post");
    document.body.appendChild(modal);
    let opener = null;

    function open(post) {
      opener = document.activeElement;
      const close = document.createElement("button");
      close.type = "button";
      close.className = "news-modal-close";
      close.setAttribute("aria-label", "Close");
      close.textContent = "×";
      close.addEventListener("click", () => modal.close());
      const full = post.cloneNode(true);
      full.querySelectorAll(".news-more, .news-nav, .news-dots").forEach(b => b.remove());
      full.querySelectorAll(".is-cut").forEach(el => el.classList.remove("is-cut"));
      full.querySelectorAll("img").forEach(img => img.removeAttribute("loading"));
      modal.replaceChildren(close, ...full.childNodes);
      openExternalLinksInNewTab();
      modal.showModal();
      modal.scrollTop = 0;
      // Open the slideshow on the same picture the card was showing.
      const from = post.querySelector(".news-carousel .news-track");
      const to = modal.querySelector(".news-carousel");
      if (to) {
        initCarousel(to);
        if (from) to.querySelector(".news-track").scrollTo({
          left: Math.round(from.scrollLeft / from.clientWidth) * to.clientWidth, behavior: "instant"
        });
      }
      close.focus();
    }

    modal.addEventListener("click", e => { if (e.target === modal) modal.close(); }); // click outside
    modal.addEventListener("close", () => { if (opener) opener.focus(); });

    function measure() {
      posts.forEach(post => {
        const text = post.querySelector(".news-text");
        const more = post.querySelector(".news-more");
        if (!text || !more) return;
        const cut = text.scrollHeight > text.clientHeight + 2;
        text.classList.toggle("is-cut", cut);
        post.classList.toggle("has-more", cut);
        more.hidden = !cut;
      });
    }
    document.querySelectorAll(".news-list .news-carousel").forEach(initCarousel);
    posts.forEach(post => {
      // The corner icon is the keyboard / screen-reader way in; a click anywhere
      // on the card does the same, except on its links and slideshow buttons.
      const more = post.querySelector(".news-more");
      if (more) {
        more.setAttribute("aria-label", "Read the whole post");
        more.title = "Read the whole post";
        more.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" ' +
          'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<path d="M9.5 2.5h4v4M13.5 2.5 9 7M6.5 13.5h-4v-4M2.5 13.5 7 9"/></svg>';
      }
      post.addEventListener("click", e => {
        if (e.target.closest("a, button:not(.news-more)")) return;
        if (String(window.getSelection())) return; // selecting text, not opening
        open(post);
      });
    });
    measure();
    window.addEventListener("resize", measure);
    if (document.fonts) document.fonts.ready.then(measure);
  }

  initEvents();
  initNews();

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
