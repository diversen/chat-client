import { initTopMenuOverlay } from '/static/js/top-menu-overlay.js';
import { Flash } from '/static/js/flash.js';
import { initShortcuts } from '/static/js/short-cuts.js';

function initBasePage() {
    initTopMenuOverlay();
    initShortcuts();

    Flash.removeAfterSecs = 10;
    Flash.clearMessages();
}

export { initBasePage };
