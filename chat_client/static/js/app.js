import { mdNoHTML } from './markdown.js';
import { getConfig } from './app-dialog.js';
import {
    loadingSpinner,
} from './app-elements.js';
import { initAppEvents } from './app-events.js';
import { dd } from './diff-dom.js';
import { modifyStreamedText } from './utils.js';
import { createStorageService, createAuthService, createChatService } from './chat-services.js';
import { ConversationController } from './chat-controller.js';
import { createChatView } from './chat-view.js';

initAppEvents();
const config = await getConfig();

// Math rendering
const useKatex = config.use_katex;

/**
 * Helper function: Highlight code in a given element
 */
function highlightCodeInElement(element) {
    const codeBlocks = element.querySelectorAll('pre code');
    codeBlocks.forEach(hljs.highlightElement);
}

/**
 * Render math if enabled
 */
function renderKatex(contentElem) {
    // This is not working optimally. 
    // LLMs might produce sentences like: 
    // a) (sufficiently well-behaved) or
    // b) ( e^{i\omega t} ).
    // 
    // Besides that markdown usually also escapes the backslash
    // and this may mess up rendering.
    //
    // Fix matrix rendering. This be done like this:
    // Replace '\\' with '\\cr'
    if (useKatex) {
        renderMathInElement(contentElem, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "$", right: "$", display: false },
                { left: "\\(", right: "\\)", display: false },
                { left: "\\begin{equation}", right: "\\end{equation}", display: true },
                { left: "\\begin{align}", right: "\\end{align}", display: true },
                { left: "\\begin{alignat}", right: "\\end{alignat}", display: true },
                { left: "\\begin{gather}", right: "\\end{gather}", display: true },
                { left: "\\begin{CD}", right: "\\end{CD}", display: true },
                { left: "\\[", right: "\\]", display: true },
            ],
        });
    }
}

/**
 * Render streamed response text into the content element (static render)
 * Note: renamed from renderSteamedResponseText
 */
async function renderStreamedResponseText(contentElement, streamedResponseText) {
    const startTime = performance.now();

    streamedResponseText = modifyStreamedText(streamedResponseText);
    contentElement.innerHTML = mdNoHTML.render(streamedResponseText);

    // Optimize highlight and KaTeX: run after markdown render
    highlightCodeInElement(contentElement);
    renderKatex(contentElement);

    const endTime = performance.now();
    console.log(`Time spent: ${endTime - startTime} milliseconds`);
}

/**
 * rAF-based coalesced diff scheduler
 * Ensures we do at most one diff/apply per frame, and supports a forced immediate flush.
 */
let rafScheduled = false;
let pendingArgs = null;

async function flushDiff() {
    if (!pendingArgs) return;
    const { contentElement, hiddenContentElem, streamedResponseText } = pendingArgs;
    pendingArgs = null;

    await renderStreamedResponseText(hiddenContentElem, streamedResponseText);

    try {
        const diff = dd.diff(contentElement, hiddenContentElem);
        if (diff.length) dd.apply(contentElement, diff);
    } catch (error) {
        console.log("Error in diffDOMExec:", error);
    }
    rafScheduled = false;
}

function scheduleDiff(contentElement, hiddenContentElem, streamedResponseText) {
    pendingArgs = { contentElement, hiddenContentElem, streamedResponseText };
    if (rafScheduled) return;
    rafScheduled = true;
    // Double rAF to push after current layout/paint for smoother UX
    requestAnimationFrame(() => requestAnimationFrame(() => { flushDiff(); }));
}

/**
 * Update the visible content by diffing against a hidden render.
 * - When force=true, flush immediately (used on finalize).
 * - Otherwise, coalesce updates to one per animation frame.
 */
async function updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, force = false) {
    if (force) {
        pendingArgs = { contentElement, hiddenContentElem, streamedResponseText };
        await flushDiff();
        return;
    }
    scheduleDiff(contentElement, hiddenContentElem, streamedResponseText);
}

const view = createChatView({
    config,
    renderStreamedResponseText,
    updateContentDiff,
});

const storageService = createStorageService();
const authService = createAuthService();
const chatService = createChatService();

/**
 * Bootstrap: instantiate controller and perform initial URL-based loading
 */
const controller = new ConversationController({
    view,
    storage: storageService,
    auth: authService,
    chat: chatService,
    config,
});

/**
 * Get the dialog ID from the URL and load the conversation
 * This only happens on page load
 */
const url = new URL(window.location.href);
const promptID = url.searchParams.get('id');
const dialogID = url.pathname.split('/').pop();

if (promptID) {
    // If we’re starting from a prompt, create the dialog and clean the URL.
    loadingSpinner.classList.remove('hidden');
    await controller.initializeFromPrompt(promptID);
    loadingSpinner.classList.add('hidden');
} else if (dialogID) {
    // Only load an existing dialog if there is no promptID
    controller.dialogId = dialogID;
    loadingSpinner.classList.remove('hidden');
    await controller.initializeDialog(controller.dialogId);
    loadingSpinner.classList.add('hidden');
}
