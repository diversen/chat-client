const registeredMenus = [];
let globalListenersAttached = false;

function isMenuOpen(menu) {
    return menu.isActive === true;
}

function hasActiveMenuForPanel(panel) {
    return registeredMenus.some((menu) => menu.panel === panel && menu.isActive === true);
}

function closeMenu(menu) {
    if (!isMenuOpen(menu)) {
        return;
    }

    menu.isActive = false;
    menu.trigger.setAttribute('aria-expanded', 'false');
    if (menu.onClose) {
        menu.onClose();
    }
    if (!hasActiveMenuForPanel(menu.panel)) {
        menu.panel.style.display = 'none';
    }
}

function closeAllTopMenus(exceptMenu = null) {
    registeredMenus.forEach((menu) => {
        if (menu !== exceptMenu) {
            closeMenu(menu);
        }
    });
}

async function openMenu(menu) {
    if (menu.beforeOpen) {
        const shouldOpen = await menu.beforeOpen();
        if (shouldOpen === false) {
            return false;
        }
    }

    closeAllTopMenus(menu);
    menu.panel.style.display = 'block';
    menu.isActive = true;
    menu.trigger.setAttribute('aria-expanded', 'true');
    if (menu.onOpen) {
        menu.onOpen();
    }
    return true;
}

async function toggleMenu(menu) {
    if (isMenuOpen(menu)) {
        closeMenu(menu);
        return;
    }

    await openMenu(menu);
}

function attachGlobalListeners() {
    if (globalListenersAttached) {
        return;
    }
    globalListenersAttached = true;

    document.addEventListener('click', function (event) {
        registeredMenus.forEach((menu) => {
            if (!isMenuOpen(menu)) {
                return;
            }

            const clickedInsideTrigger = menu.trigger.contains(event.target);
            const clickedInsidePanel = menu.panel.contains(event.target);
            if (!clickedInsideTrigger && !clickedInsidePanel) {
                closeMenu(menu);
            }
        });
    });

    window.addEventListener('pageshow', function (e) {
        if (e.persisted) {
            closeAllTopMenus();
        }
    });
}

function registerTopMenu({
    trigger,
    panel,
    beforeOpen = null,
    onOpen = null,
    onClose = null,
}) {
    if (!trigger || !panel) {
        return null;
    }

    const menu = {
        trigger,
        panel,
        beforeOpen,
        onOpen,
        onClose,
        isActive: false,
    };

    registeredMenus.push(menu);
    attachGlobalListeners();

    trigger.addEventListener('click', async function (event) {
        event.preventDefault();

        try {
            await toggleMenu(menu);
        } catch (error) {
            console.error('Error toggling top menu:', error);
        }
    });

    return {
        close: () => closeMenu(menu),
        open: () => openMenu(menu),
        toggle: () => toggleMenu(menu),
    };
}

export { registerTopMenu, closeAllTopMenus };
