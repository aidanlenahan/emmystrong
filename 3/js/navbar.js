// Dynamically load the navbar from partials/navbar.html
document.addEventListener("DOMContentLoaded", () => {
    fetch("partials/navbar.html")
        .then(response => response.text())
        .then(html => {
            document.getElementById("navbar").innerHTML = html;
        })
        .catch(err => console.error("Failed to load navbar:", err));
});
