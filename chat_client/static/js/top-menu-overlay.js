import { registerTopMenu } from '/static/js/top-menu-controller.js';

function initTopMenuOverlay() {
    const topMenuOverlay = document.querySelector('.top-menu-overlay');
    const mainMenuButton = document.getElementById('main-menu-hamburger');
    const customPromptsButton = document.getElementById('new-from-custom');
    const menuOpen = document.querySelector('.menu-open');
    const menuClosed = document.querySelector('.menu-closed');

    if (!topMenuOverlay || !mainMenuButton || !menuOpen || !menuClosed) {
        return;
    }

    const mainPanel = topMenuOverlay.querySelector('.top-menu-panel-main');
    const promptsPanel = topMenuOverlay.querySelector('.top-menu-panel-prompts');
    if (!mainPanel) {
        return;
    }

    function setMode(mode) {
        topMenuOverlay.setAttribute('data-mode', mode);
    }

    registerTopMenu({
        trigger: mainMenuButton,
        panel: topMenuOverlay,
        onOpen: function () {
            setMode('main');
            menuOpen.style.display = 'block';
            menuClosed.style.display = 'none';
        },
        onClose: function () {
            menuOpen.style.display = 'none';
            menuClosed.style.display = 'block';
        },
    });

    if (customPromptsButton && promptsPanel) {
        registerTopMenu({
            trigger: customPromptsButton,
            panel: topMenuOverlay,
            beforeOpen: async function () {
                try {
                    const response = await fetch('/prompt/json');
                    if (!response.ok) {
                        throw new Error(`Failed to fetch prompts: ${response.status}`);
                    }

                    const data = await response.json();
                    if (data.error) {
                        console.error('Error fetching prompts:', data.message);
                        return false;
                    }

                    if (!promptsPanel.querySelector('.overlay-header')) {
                        return false;
                    }

                    promptsPanel.querySelectorAll('.prompt-item, .no-prompts-message').forEach((item) => {
                        item.remove();
                    });

                    if (data.prompts && data.prompts.length > 0) {
                        data.prompts.forEach((prompt) => {
                            const promptLink = document.createElement('a');
                            promptLink.href = `/?id=${prompt.prompt_id}`;
                            promptLink.textContent = prompt.title;
                            promptLink.className = 'prompt-item';
                            promptsPanel.appendChild(promptLink);
                        });
                    } else {
                        const createPromptLink = document.createElement('a');
                        createPromptLink.href = '/prompt/create';
                        createPromptLink.textContent = 'New Custom Prompt';
                        createPromptLink.className = 'no-prompts-message';
                        promptsPanel.appendChild(createPromptLink);
                    }

                    return true;
                } catch (error) {
                    console.error('Error loading custom prompts:', error);
                    return false;
                }
            },
            onOpen: function () {
                setMode('prompts');
            },
        });
        customPromptsButton.setAttribute('aria-expanded', 'false');
    }

    topMenuOverlay.style.display = 'none';
    setMode('main');
    mainMenuButton.setAttribute('aria-expanded', 'false');
    menuOpen.style.display = 'none';
    menuClosed.style.display = 'block';
}

export { initTopMenuOverlay };
