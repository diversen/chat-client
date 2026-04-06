import { getConfig } from '/static/js/app-dialog.js';
import { getChatElements } from '/static/js/app-elements.js';
import { initAppEvents } from '/static/js/app-events.js';
import { attachImageIcon, attachFileIcon, sendIcon, abortIcon } from '/static/js/app-icons.js';
import { dd } from '/static/js/diff-dom.js';
import { renderKatex, renderMarkdownWithKatex } from '/static/js/katex-render.js';
import { storageService, chatService } from '/static/js/chat-services.js';
import { ConversationController } from '/static/js/chat-controller.js';
import { createChatView } from '/static/js/chat-view.js';

const elements = getChatElements();
elements.attachImageButtonElem.innerHTML = attachImageIcon;
elements.attachFileButtonElem.innerHTML = attachFileIcon;
elements.sendButtonElem.innerHTML = sendIcon;
elements.abortButtonElem.innerHTML = abortIcon;
initAppEvents(elements);
const config = await getConfig();

// Math rendering
const useKatex = config.use_katex;
const STREAM_RENDER_CONFIG = {
    runHighlightOnUpdate: false,
    runHighlightOnFinalize: true,
    runKatexOnUpdate: false,
    runKatexOnFinalize: true,
};

/**
 * Helper function: Highlight code in a given element
 */
function highlightCodeInElement(element) {
    const codeBlocks = element.querySelectorAll('pre code');
    codeBlocks.forEach(hljs.highlightElement);
}

function shouldRunHighlight(isFinal = true) {
    return isFinal
        ? STREAM_RENDER_CONFIG.runHighlightOnFinalize
        : STREAM_RENDER_CONFIG.runHighlightOnUpdate;
}

function shouldRunKatex(isFinal = true) {
    if (!useKatex) return false;
    return isFinal
        ? STREAM_RENDER_CONFIG.runKatexOnFinalize
        : STREAM_RENDER_CONFIG.runKatexOnUpdate;
}

function appendRenderedMarkdown(target, markdownText) {
    if (useKatex) {
        renderMarkdownWithKatex(target, markdownText);
        return;
    }

    const container = document.createElement('div');
    container.innerHTML = mdNoHTML.render(modifyStreamedText(markdownText));
    while (container.firstChild) {
        target.appendChild(container.firstChild);
    }
}

/**
 * Render streamed response text into the content element (static render)
 * Note: renamed from renderSteamedResponseText
 */
async function renderStreamedResponseText(contentElement, streamedResponseText, isFinal = true) {
    const startTime = performance.now();

    contentElement.innerHTML = '';
    appendRenderedMarkdown(contentElement, streamedResponseText);

    // Expensive post-processing can be tuned independently for update/finalize.
    if (shouldRunHighlight(isFinal)) {
        highlightCodeInElement(contentElement);
    }
    if (shouldRunKatex(isFinal)) {
        renderKatex(contentElement, useKatex);
    }

    const endTime = performance.now();
    console.log(`Time spent: ${endTime - startTime} milliseconds`);
}

/**
 * rAF-based coalesced diff scheduler
 * Ensures we do at most one diff/apply per frame, and supports a forced immediate flush.
 */
let rafScheduled = false;
let pendingArgs = null;
let pendingFlushResolvers = [];

async function flushDiff() {
    if (!pendingArgs) {
        const resolvers = pendingFlushResolvers;
        pendingFlushResolvers = [];
        resolvers.forEach((resolve) => resolve());
        return;
    }
    const { contentElement, hiddenContentElem, streamedResponseText, isFinal } = pendingArgs;
    pendingArgs = null;

    await renderStreamedResponseText(hiddenContentElem, streamedResponseText, isFinal);

    try {
        const diff = dd.diff(contentElement, hiddenContentElem);
        if (diff.length) dd.apply(contentElement, diff);
    } catch (error) {
        console.log("Error in diffDOMExec:", error);
    }
    rafScheduled = false;
    const resolvers = pendingFlushResolvers;
    pendingFlushResolvers = [];
    resolvers.forEach((resolve) => resolve());
}

function scheduleDiff(contentElement, hiddenContentElem, streamedResponseText, isFinal = false) {
    pendingArgs = { contentElement, hiddenContentElem, streamedResponseText, isFinal };
    const flushPromise = new Promise((resolve) => {
        pendingFlushResolvers.push(resolve);
    });
    if (!rafScheduled) {
        rafScheduled = true;
        // Double rAF to push after current layout/paint for smoother UX
        requestAnimationFrame(() => requestAnimationFrame(() => { flushDiff(); }));
    }
    return flushPromise;
}

/**
 * Update the visible content by diffing against a hidden render.
 * - When force=true, flush immediately (used on finalize).
 * - Otherwise, coalesce updates to one per animation frame.
 */
async function updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, force = false) {
    if (force) {
        pendingArgs = { contentElement, hiddenContentElem, streamedResponseText, isFinal: true };
        await flushDiff();
        return;
    }
    await scheduleDiff(contentElement, hiddenContentElem, streamedResponseText, false);
}

const view = createChatView({
    config,
    elements,
    renderStreamedResponseText,
    updateContentDiff,
});

/**
 * Bootstrap: instantiate controller and perform initial URL-based loading
 */
const controller = new ConversationController({
    view,
    storage: storageService,
    chat: chatService,
    config,
    elements,
});

/**
 * Get the dialog ID from the URL and load the conversation
 * This only happens on page load
 */
const url = new URL(window.location.href);
const promptID = url.searchParams.get('id');
const dialogID = url.pathname.split('/').pop();

try {
    if (promptID) {
        // If we’re starting from a prompt, create the dialog and clean the URL.
        await controller.initializeFromPrompt(promptID);
    } else if (dialogID) {
        // Only load an existing dialog if there is no promptID
        controller.dialogId = dialogID;
        elements.loadingSpinner.classList.remove('hidden');
        await controller.initializeDialog(controller.dialogId);
        elements.loadingSpinner.classList.add('hidden');
    }
} finally {
    controller.setInitializing(false);
    elements.loadingSpinner.classList.add('hidden');
}
