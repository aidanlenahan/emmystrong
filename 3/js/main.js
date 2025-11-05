// Smooth scroll and dropdown interactivity
document.addEventListener("click", function(e) {
    const dropdown = e.target.closest(".dropdown");
    document.querySelectorAll(".dropdown").forEach(d => {
        if (d !== dropdown) d.classList.remove("active");
    });
    if (dropdown) dropdown.classList.toggle("active");
});
