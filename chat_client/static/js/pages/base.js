import { initMainMenuOverlay } from '/static/js/main-menu-overlay.js';
import { initCustomPromptsOverlay } from '/static/js/custom-prompts-overlay.js';
import { Flash } from '/static/js/flash.js';
import { initShortcuts } from '/static/js/short-cuts.js';

function initBasePage() {
    initMainMenuOverlay();
    initCustomPromptsOverlay();
    initShortcuts();

    Flash.removeAfterSecs = 10;
    Flash.clearMessages();
}

export { initBasePage };
