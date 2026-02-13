function initMainMenuOverlay() {
    const hamburgerMenu = document.getElementById('main-menu-hamburger');
    const mainMenuOverlay = document.querySelector('.main-menu-overlay');
    const menuOpen = document.querySelector('.menu-open');
    const menuClosed = document.querySelector('.menu-closed');

    if (!hamburgerMenu || !mainMenuOverlay || !menuOpen || !menuClosed) {
        return;
    }

    function closeMenu() {
        mainMenuOverlay.style.display = 'none';
        hamburgerMenu.setAttribute('aria-expanded', 'false');
        menuOpen.style.display = 'none';
        menuClosed.style.display = 'block';
    }

    hamburgerMenu.addEventListener('click', function (event) {
        event.preventDefault();

        if (mainMenuOverlay.style.display === 'none' || mainMenuOverlay.style.display === '') {
            mainMenuOverlay.style.display = 'block';
            hamburgerMenu.setAttribute('aria-expanded', 'true');
            menuOpen.style.display = 'block';
            menuClosed.style.display = 'none';
        } else {
            closeMenu();
        }
    });

    document.addEventListener('click', function (event) {
        if (!hamburgerMenu.contains(event.target) && !mainMenuOverlay.contains(event.target)) {
            closeMenu();
        }
    });

    window.addEventListener('pageshow', function (e) {
        if (e.persisted) {
            closeMenu();
        }
    });
}

export { initMainMenuOverlay };
