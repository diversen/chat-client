const hamburgerMenu = document.getElementById('main-menu-hamburger');
const mainMenuOverlay = document.querySelector('.main-menu-overlay');
const menuOpen = document.querySelector('.menu-open');
const menuClosed = document.querySelector('.menu-closed');

hamburgerMenu.addEventListener('click', function (event) {
    event.preventDefault();

    // Expand
    if (mainMenuOverlay.style.display === "none" || mainMenuOverlay.style.display === "") {
        mainMenuOverlay.style.display = "block";
        hamburgerMenu.setAttribute('aria-expanded', 'true');

        // Change icon
        menuOpen.style.display = "block";
        menuClosed.style.display = "none";
    } else {
        mainMenuOverlay.style.display = "none";
        hamburgerMenu.setAttribute('aria-expanded', 'false');

        // Change icon
        menuOpen.style.display = "none";
        menuClosed.style.display = "block";
    }
});

document.addEventListener('click', function (event) {
    if (!hamburgerMenu.contains(event.target) && !mainMenuOverlay.contains(event.target)) {
        mainMenuOverlay.style.display = "none";
        hamburgerMenu.setAttribute('aria-expanded', 'false');

        // Change icon
        menuOpen.style.display = "none";
        menuClosed.style.display = "block";
    }
});


// on pageshow event, if the menu is open, close it
window.addEventListener('pageshow', function (e) {
    if (e.persisted) {
        mainMenuOverlay.style.display = "none";
        hamburgerMenu.setAttribute('aria-expanded', 'false');

        // Change icon
        menuOpen.style.display = "none";
        menuClosed.style.display = "block";
    }
});