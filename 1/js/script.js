// Mobile nav toggle
const toggle = document.querySelector('.nav-toggle');
const nav = document.querySelector('nav ul');

toggle.addEventListener('click', () => {
    nav.classList.toggle('show');
});
