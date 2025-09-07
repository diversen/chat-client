import { Flash } from './flash.js';
import { mdNoHTML } from './markdown.js';
import { createDialog, getMessages, createMessage, getConfig, isLoggedInOrRedirect, updateMessage } from './app-dialog.js';
import { responsesElem, messageElem, sendButtonElem, newButtonElem, abortButtonElem, selectModelElem, loadingSpinner, scrollToBottom } from './app-elements.js';
import { } from './app-events.js';
import { addCopyButtons } from './app-copy-buttons.js';
import { logError } from './error-log.js';
import { dd } from './diff-dom.js';
import { modifyStreamedText } from './utils.js';
import { copyIcon, checkIcon, editIcon } from './app-icons.js';

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

/**
 * Create a message element with role and content
 */
function createMessageElement(role, messageId = null) {
    const containerClass = `${role.toLowerCase()}-message`;
    const messageContainer = document.createElement('div');
    messageContainer.classList.add(containerClass);

    // Store message ID as data attribute if provided
    if (messageId) {
        messageContainer.setAttribute('data-message-id', messageId);
    }

    // Use template literals to create the HTML structure
    messageContainer.innerHTML = `
    <h3 class="role role_${role.toLowerCase()}">
      ${role}
      <div class="loading-model hidden"></div>
    </h3>
    <div class="content"></div>
    <div class="message-actions hidden">
      <a href="#" class="copy-message" title="Copy message to clipboard">
        ${copyIcon}
      </a>
    </div>
  `;

    // Select the elements from the generated HTML
    const loaderSpan = messageContainer.querySelector('.loading-model');
    const contentElement = messageContainer.querySelector('.content');

    return { container: messageContainer, contentElement: contentElement, loader: loaderSpan };
}

function renderCopyMessageButton(container, message) {

    const messageActions = container.querySelector('.message-actions');
    messageActions.classList.remove('hidden');
    messageActions.querySelector('.copy-message').addEventListener('click', () => {
        // Notice this will only work in secure contexts (HTTPS)
        navigator.clipboard.writeText(message);

        // Alter icon to check icon for 3 seconds
        const copyButton = messageActions.querySelector('.copy-message');
        copyButton.innerHTML = checkIcon;
        setTimeout(() => {
            copyButton.innerHTML = copyIcon;
        }, 2000);
    });
}

/**
 * View: DOM-only utilities (no state)
 */
const view = {
    /**
     * Render user message to the DOM
     */
    renderStaticUserMessage(message, messageId = null, onEdit) {
        const { container, contentElement } = createMessageElement('User', messageId);
        contentElement.style.whiteSpace = 'pre-wrap';
        contentElement.innerText = message;
        renderCopyMessageButton(container, message);

        // Render edit message button for user messages (only if we have a message ID)
        if (messageId) {
            renderEditMessageButton(container, message, onEdit);
        }
        responsesElem.appendChild(container);
    },

    /**
     * Render static assistant message (without streaming)
     */
    async renderStaticAssistantMessage(message, messageId = null) {
        const { container, contentElement } = createMessageElement('Assistant', messageId);
        responsesElem.appendChild(container);
        renderCopyMessageButton(container, message);
        await renderStreamedResponseText(contentElement, message);
        await addCopyButtons(contentElement, config);
    },

    /**
     * Create a new assistant container for streaming
     */
    createAssistantContainer() {
        const { container, contentElement, loader } = createMessageElement('Assistant');
        responsesElem.appendChild(container);
        loader.classList.remove('hidden');

        const hiddenContentElem = document.createElement('div');
        hiddenContentElem.classList.add('content');
        contentElement.classList.add('content');

        let streamedResponseText = '';
        let reasoningActive = false;

        return {
            container,
            loader,
            hiddenContentElem,
            contentElement,
            appendReasoning(text) {
                if (!reasoningActive) {
                    streamedResponseText += '<thinking>\n';
                    reasoningActive = true;
                }
                streamedResponseText += text;
            },
            closeReasoningIfOpen() {
                if (reasoningActive) {
                    streamedResponseText += ' </thinking>\n\n';
                    reasoningActive = false;
                }
            },
            async appendContent(text, force = false) {
                streamedResponseText += text;
                await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, force);
            },
            async finalize() {
                this.closeReasoningIfOpen();
                await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, true);
                return streamedResponseText;
            }
        };
    },

    /**
     * UI state helpers
     */
    showLoader(container) {
        const loader = container.querySelector('.loading-model');
        if (loader) loader.classList.remove('hidden');
    },
    hideLoader(container) {
        const loader = container.querySelector('.loading-model');
        if (loader) loader.classList.add('hidden');
    },
    clearInput() { messageElem.value = ''; },
    disableSend() { sendButtonElem.setAttribute('disabled', true); },
    enableSend() { sendButtonElem.removeAttribute('disabled'); },
    disableNew() { newButtonElem.setAttribute('disabled', true); },
    enableNew() { newButtonElem.removeAttribute('disabled'); },
    disableAbort() { abortButtonElem.setAttribute('disabled', true); },
    enableAbort() { abortButtonElem.removeAttribute('disabled'); },
    getSelectedModel() { return selectModelElem.value; },
    attachCopy(container, text) { renderCopyMessageButton(container, text); },
    scrollToLastMessage() {
        responsesElem.scrollTo({ top: responsesElem.scrollHeight, behavior: 'smooth' });
    },
};

/**
 * Render edit message button (delegates callback to controller)
 */
function renderEditMessageButton(container, originalMessage, onEdit) {
    const messageActions = container.querySelector('.message-actions');

    // Add edit button next to copy button
    const editButton = document.createElement('a');
    editButton.href = '#';
    editButton.className = 'edit-message';
    editButton.title = 'Edit message';
    editButton.innerHTML = editIcon;
    messageActions.appendChild(editButton);

    editButton.addEventListener('click', (e) => {
        e.preventDefault();
        showEditForm(container, originalMessage, onEdit);
    });
}

function showEditForm(container, originalMessage, onEdit) {
    const contentElement = container.querySelector('.content');
    const messageActions = container.querySelector('.message-actions');

    // Hide original content and actions
    contentElement.style.display = 'none';
    messageActions.style.display = 'none';

    // Create edit form
    const editForm = document.createElement('div');
    editForm.className = 'edit-form';
    editForm.innerHTML = `
    <textarea class="edit-textarea">${originalMessage}</textarea>
    <div class="edit-buttons">
      <button class="edit-cancel">Cancel</button>
      <button class="edit-send">Send</button>
    </div>
  `;

    // Insert edit form after content
    contentElement.insertAdjacentElement('afterend', editForm);

    const textarea = editForm.querySelector('.edit-textarea');
    const cancelButton = editForm.querySelector('.edit-cancel');
    const sendButton = editForm.querySelector('.edit-send');

    // Focus and resize textarea
    textarea.focus();
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';

    // Cancel button handler
    cancelButton.addEventListener('click', () => {
        hideEditForm(container);
    });

    // Send button handler
    sendButton.addEventListener('click', async () => {
        const newContent = textarea.value.trim();
        if (!newContent) {
            alert('Message content cannot be empty');
            return;
        }
        const messageId = container.getAttribute('data-message-id');
        if (!messageId) {
            alert('Cannot edit message: message ID not found');
            return;
        }
        try {
            sendButton.disabled = true;
            sendButton.textContent = 'Sending...';
            await onEdit(messageId, newContent, container);
        } catch (error) {
            console.error('Error updating message:', error);
            alert('Error updating message. Please try again.');
            sendButton.disabled = false;
            sendButton.textContent = 'Send';
        }
    });
}

function hideEditForm(container) {
    const contentElement = container.querySelector('.content');
    const messageActions = container.querySelector('.message-actions');
    const editForm = container.querySelector('.edit-form');

    // Remove edit form
    if (editForm) {
        editForm.remove();
    }

    // Show original content and actions
    contentElement.style.display = '';
    messageActions.style.display = '';
}

/**
 * Services: extracted external dependencies (injected into controller)
 */
const storageService = {
    async createDialog(title) { return await createDialog(title); },
    async createMessage(dialogId, msg) { return await createMessage(dialogId, msg); },
    async updateMessage(id, text) { return await updateMessage(id, text); },
    async getMessages(dialogId) { return await getMessages(dialogId); }
};

const authService = {
    async ensure() { return await isLoggedInOrRedirect(); }
};

/**
 * SSE stream parser and fetch wrapper
 */
const chatService = {
    async *stream(payload, signal) {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal,
        });
        if (!response.ok) {
            throw new Error(`Server returned error: ${response.status} ${response.statusText}`);
        }
        if (!response.body) {
            throw new Error('Response body is empty. Try again later.');
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let reasoningOpen = false;
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const lines = decoder.decode(value, { stream: true }).split('\n').filter(Boolean);
            for (const rawLine of lines) {
                const line = rawLine.replace(/^data:\s*/, '').trim();
                if (line === '[DONE]') {
                    if (reasoningOpen) {
                        yield { reasoning: null, reasoningOpenClose: 'close' };
                        reasoningOpen = false;
                    }
                    return;
                }
                let data;
                try { data = JSON.parse(line); } catch (_) { continue; }
                const delta = data.choices?.[0]?.delta ?? {};
                const finishReason = data.choices?.[0]?.finish_reason;

                if (delta.reasoning) {
                    if (!reasoningOpen) {
                        yield { reasoning: null, reasoningOpenClose: 'open' };
                        reasoningOpen = true;
                    }
                    yield { reasoning: delta.reasoning };
                } else if (reasoningOpen) {
                    yield { reasoning: null, reasoningOpenClose: 'close' };
                    reasoningOpen = false;
                }
                if (delta.content) yield { content: delta.content };
                if (finishReason) yield { done: true };
            }
        }
    }
};

/**
 * Conversation controller: owns all state and side-effects
 */
class ConversationController {
    /**
     * @param {{
     *   view: typeof view,
     *   storage: typeof storageService,
     *   auth: typeof authService,
     *   chat: typeof chatService
     * }} params
     */
    constructor({ view, storage, auth, chat }) {
        /** @type {typeof view} */
        this.view = view;
        /** @type {typeof storageService} */
        this.storage = storage;
        /** @type {typeof authService} */
        this.auth = auth;
        /** @type {typeof chatService} */
        this.chat = chat;
        /** @type {boolean} */
        this.isStreaming = false;
        /** @type {Array<Object>} */
        this.messages = [];
        /** @type {string|null} */
        this.dialogId = null;
        /** @type {AbortController} */
        this.abortController = new AbortController();

        // Bind UI once
        this.wireUI();
    }

    /**
     * Shortcut to send message when user presses Enter + Ctrl
     */
    wireUI() {
        // Add event listener to the send button
        sendButtonElem.addEventListener('click', async () => {
            await this.sendUserMessage();
        });

        /**
         * Add event listener to the abort button
         */
        abortButtonElem.addEventListener('click', () => {
            console.log('Aborting request');
            this.abortController.abort();
            this.abortController = new AbortController();
        });

        /**
         * Shortcut to send message when user presses Enter + Ctrl
         */
        messageElem.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter') {
                if (e.ctrlKey) {
                    // If Ctrl+Enter is pressed, add a new line at the point of the cursor
                    e.preventDefault();
                    const start = messageElem.selectionStart;
                    const end = messageElem.selectionEnd;
                    messageElem.value = messageElem.value.substring(0, start) + '\n' + messageElem.value.substring(end);
                    messageElem.selectionStart = messageElem.selectionEnd = start + 1;
                } else {
                    // If only Enter is pressed, prevent the default behavior and send the message
                    e.preventDefault();
                    await this.sendUserMessage();
                }
            }
        });

        // Scroll helpers and UX affordance (unchanged behavior)
        let userInteracting = false;
        let interactionTimeout;

        // Listen for wheel on window
        window.addEventListener('wheel', () => {
            userInteracting = true;
            scrollToBottom.style.display = 'none';
            clearTimeout(interactionTimeout);
            interactionTimeout = setTimeout(() => {
                userInteracting = false;
                this.checkScroll(userInteracting);
            }, 1000);
        });

        // Listen for touchstart and touchend on responsesElem
        responsesElem.addEventListener('touchstart', () => {
            userInteracting = true;
            scrollToBottom.style.display = 'none';
            clearTimeout(interactionTimeout); // clear if touchstart happens again
        });

        responsesElem.addEventListener('touchend', () => {
            clearTimeout(interactionTimeout);
            interactionTimeout = setTimeout(() => {
                userInteracting = false;
                this.checkScroll(userInteracting);
            }, 1000);
        });

        responsesElem.addEventListener('scroll', () => this.checkScroll(userInteracting));
        new MutationObserver(() => this.checkScroll(userInteracting)).observe(responsesElem, { childList: true, subtree: true });
    }

    checkScroll(userInteracting) {
        const threshold = 2; // px tolerance
        const atBottom = Math.abs(responsesElem.scrollHeight - responsesElem.scrollTop - responsesElem.clientHeight) <= threshold;
        const hasScrollbar = responsesElem.scrollHeight > responsesElem.clientHeight;

        if (hasScrollbar && !atBottom && !userInteracting) {
            scrollToBottom.style.display = 'flex';
        } else {
            scrollToBottom.style.display = 'none';
        }
    }

    /**
     * Validate user message
     */
    validateUserMessage(userMessage) {
        if (!userMessage || this.isStreaming) {
            console.log('Empty message or assistant is streaming');
            return false;
        }
        return true;
    }

    /**
     * Send user message to the server and render the response
     */
    async sendUserMessage() {
        try {
            await this.auth.ensure();
            const userMessage = messageElem.value.trim();
            if (!this.validateUserMessage(userMessage)) return;

            // Save as dialog if it's the first message
            const message = { role: 'user', content: userMessage };

            // Create new dialog if there are no messages
            if (this.messages.length === 0) {
                this.dialogId = await this.storage.createDialog(userMessage);
            }

            // Push user message to current dialog messages
            this.messages.push(message);

            // Save user message and get the message ID
            const userMessageId = await this.storage.createMessage(this.dialogId, message);

            // Clear the input field
            this.view.clearInput();

            // Render user message
            view.renderStaticUserMessage(userMessage, userMessageId, async (id, newContent, container) => {
                await this.handleMessageUpdate(id, newContent, container);
            });

            // Scroll so that last user message is visible
            this.view.scrollToLastMessage();

            await this.renderAssistantMessage();
        } catch (error) {
            await logError(error, 'Error in sendUserMessage');
            console.error('Error in sendUserMessage:', error);
            Flash.setMessage('An error occurred. Please try again.', 'error');
        }
    }

    /**
     * Handle user message update (edit and regenerate)
     */
    async handleMessageUpdate(messageId, newContent, container) {
        try {
            // Update message on server
            await this.storage.updateMessage(messageId, newContent);

            // Update the content element with new content
            const contentElement = container.querySelector('.content');
            contentElement.style.whiteSpace = 'pre-wrap';
            contentElement.innerText = newContent;

            // Hide edit form and show updated content
            hideEditForm(container);

            // Remove all messages after this one from DOM and messages array
            this.removeMessagesAfter(container);

            // Update messages array by ID
            this.updateMessagesArray(messageId, newContent);

            // Start new assistant response
            await this.renderAssistantMessage();
        } catch (error) {
            throw error;
        }
    }

    removeMessagesAfter(editedContainer) {
        let nextSibling = editedContainer.nextElementSibling;
        while (nextSibling) {
            const toRemove = nextSibling;
            nextSibling = nextSibling.nextElementSibling;
            toRemove.remove();
        }
    }

    updateMessagesArray(editedMessageId, newContent) {
        const index = this.messages.findIndex(m => m.message_id === editedMessageId || m.id === editedMessageId);
        if (index !== -1) {
            if (this.messages[index]) this.messages[index].content = newContent;
            this.messages.splice(index + 1);
        }
    }

    /**
     * Render assistant message with streaming
     */
    async renderAssistantMessage() {
        // Create container for assistant message and content element
        const ui = view.createAssistantContainer();
        this.view.disableSend();
        this.view.disableNew();
        this.view.enableAbort();
        this.isStreaming = true;

        try {
            for await (const chunk of this.chat.stream({ model: this.view.getSelectedModel(), messages: this.messages }, this.abortController.signal)) {
                // hide the loader on first payload
                ui.loader.classList.add('hidden');

                if (chunk.reasoningOpenClose === 'open') {
                    ui.appendReasoning('');
                } else if (chunk.reasoningOpenClose === 'close') {
                    ui.closeReasoningIfOpen();
                }
                if (chunk.reasoning) {
                    await ui.appendContent(chunk.reasoning);
                }
                if (chunk.content) {
                    await ui.appendContent(chunk.content, Boolean(chunk.done));
                }
            }
        } catch (error) {
            ui.loader.classList.add('hidden');
            if (error.name === 'AbortError') {
                Flash.setMessage('Request was aborted', 'notice');
                console.log('Request was aborted');
            } else {
                console.error('Error in processStream:', error);
                Flash.setMessage('An error occurred while processing the stream.', 'error');
            }
        } finally {
            // Clear streaming
            console.log('Clearing streaming');
            this.isStreaming = false;
            this.view.disableAbort();
            this.view.disableSend();
            this.view.enableNew();

            // wait for the next frame to render
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

            const finalText = await ui.finalize();

            // Enable buttons and enrich content
            await addCopyButtons(ui.contentElement, config);

            // Save message to the dialog
            let assistantMessage = { role: 'assistant', content: finalText };
            const assistantMessageId = await this.storage.createMessage(this.dialogId, assistantMessage);

            // Store the message ID in the container
            ui.container.setAttribute('data-message-id', assistantMessageId);

            // Render copy message
            view.attachCopy(ui.container, finalText);

            this.messages.push({ ...assistantMessage, message_id: assistantMessageId });

            // reset abort controller for next run
            this.abortController = new AbortController();
            this.view.enableSend();
        }
    }

    /**
     * Load a saved conversation
     */
    async loadDialog(savedMessages) {
        this.messages = savedMessages.slice();
        responsesElem.innerHTML = '';

        for (const msg of this.messages) {
            if (msg.role === 'user') {
                const message = msg.content;
                const messageId = msg.message_id;
                view.renderStaticUserMessage(message, messageId, async (id, newContent, container) => {
                    await this.handleMessageUpdate(id, newContent, container);
                });
            } else {
                const message = msg.content;
                const messageId = msg.message_id;
                await view.renderStaticAssistantMessage(message, messageId);
            }
        }
    }

    /**
     * Initialize the dialog
     */
    async initializeDialog(dialogID) {
        try {
            let allMessages = await this.storage.getMessages(dialogID);
            console.log('All messages:', allMessages);
            await this.loadDialog(allMessages);
        } catch (error) {
            console.error('Error in initializeDialog:', error);
            Flash.setMessage('An error occurred. Please try again.', 'error');
        }
    }

    async initializeFromPrompt(promptID) {
        console.log('Initializing from prompt ID:', promptID);
        try {
            const response = await fetch(`/prompt/${promptID}/json`);
            if (!response.ok) {
                throw new Error(`Failed to fetch prompt: ${response.status} ${response.statusText}`);
            }
            const promptData = await response.json();
            const promptText = promptData.prompt.prompt;

            // Create a new dialog with the prompt text
            this.dialogId = await this.storage.createDialog(promptText);

            // Save the prompt message to the dialog
            const promptMessage = { role: 'user', content: promptText };
            await this.storage.createMessage(this.dialogId, promptMessage);
            await controller.initializeDialog(this.dialogId);


        } catch (error) {
            console.error('Error in initializeFromPrompt:', error);
            Flash.setMessage('An error occurred while initializing from prompt.', 'error');
        }
    }
}

/**
 * Bootstrap: instantiate controller and perform initial URL-based loading
 */
const controller = new ConversationController({ view, storage: storageService, auth: authService, chat: chatService });

/**
 * Get the dialog ID from the URL and load the conversation
 * This only happens on page load
 */
const url = new URL(window.location.href);
const dialogID = url.pathname.split('/').pop();
if (dialogID) {
    controller.dialogId = dialogID;
    loadingSpinner.classList.remove('hidden');

    console.log('Current dialog ID:', controller.dialogId);
    await controller.initializeDialog(controller.dialogId);

    loadingSpinner.classList.add('hidden');
}

const promptID = url.searchParams.get('id');
if (promptID) {
    await controller.initializeFromPrompt(promptID);
}
