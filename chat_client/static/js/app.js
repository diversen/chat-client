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

// States
let isStreaming = false;
let currentDialogMessages = [];
let currentDialogID;

// Add event listener to the send button
sendButtonElem.addEventListener('click', async () => {
    await sendUserMessage();
});

/**
 * Set an interval to update the markdown rendering
 */
function clearStreaming() {
    console.log('Clearing streaming');
    isStreaming = false;
    abortButtonElem.setAttribute('disabled', true);
    sendButtonElem.setAttribute('disabled', true);
    newButtonElem.removeAttribute('disabled');
}

/**
 * Add event listener to the abort button
 */

let controller = new AbortController();
abortButtonElem.addEventListener('click', () => {
    console.log('Aborting request');
    controller.abort();
    controller = new AbortController();
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
            await sendUserMessage();
        }
    }
});
/**
 * Helper function: Highlight code in a given element
 */
function highlightCodeInElement(element) {
    const codeBlocks = element.querySelectorAll('pre code');
    codeBlocks.forEach(hljs.highlightElement);
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

function renderEditMessageButton(container, originalMessage) {
    const messageActions = container.querySelector('.message-actions');
    
    // Add edit button next to copy button
    const editButton = document.createElement('a');
    editButton.href = '#';
    editButton.className = 'edit-message';
    editButton.title = 'Edit message';
    editButton.innerHTML = editIcon;
    messageActions.appendChild(editButton);
    
    const contentElement = container.querySelector('.content');
    
    editButton.addEventListener('click', (e) => {
        e.preventDefault();
        showEditForm(container, originalMessage);
    });
}

function showEditForm(container, originalMessage) {
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
            
            await handleMessageUpdate(messageId, newContent, container);
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

async function handleMessageUpdate(messageId, newContent, container) {
    try {
        // Update message on server
        await updateMessage(messageId, newContent);
        
        // Update the content element with new content
        const contentElement = container.querySelector('.content');
        contentElement.style.whiteSpace = 'pre-wrap';
        contentElement.innerText = newContent;
        
        // Hide edit form and show updated content
        hideEditForm(container);
        
        // Remove all messages after this one from DOM and currentDialogMessages
        removeMessagesAfter(container);
        
        // Update currentDialogMessages array
        updateCurrentDialogMessages(messageId, newContent);
        
        // Start new assistant response
        await renderAssistantMessage();
        
    } catch (error) {
        throw error;
    }
}

function removeMessagesAfter(editedContainer) {
    let nextSibling = editedContainer.nextElementSibling;
    while (nextSibling) {
        const toRemove = nextSibling;
        nextSibling = nextSibling.nextElementSibling;
        toRemove.remove();
    }
}

function updateCurrentDialogMessages(editedMessageId, newContent) {
    // Find the index of the edited message in currentDialogMessages
    // Since we don't have message IDs in currentDialogMessages, we'll need to reconstruct it
    // For now, we'll find by looking at the position in the DOM
    const allMessages = document.querySelectorAll('.user-message, .assistant-message');
    const editedIndex = Array.from(allMessages).findIndex(msg => 
        msg.getAttribute('data-message-id') === editedMessageId
    );
    
    if (editedIndex !== -1) {
        // Update the content of the edited message
        if (currentDialogMessages[editedIndex]) {
            currentDialogMessages[editedIndex].content = newContent;
        }
        
        // Remove all messages after the edited one
        currentDialogMessages.splice(editedIndex + 1);
    }
}


/**
 * Render user message to the DOM
 */
function renderStaticUserMessage(message, messageId = null) {
    const { container, contentElement } = createMessageElement('User', messageId);

    contentElement.style.whiteSpace = 'pre-wrap';
    contentElement.innerText = message;

    // Render copy message
    renderCopyMessageButton(container, message);
    
    // Render edit message button for user messages (only if we have a message ID)
    if (messageId) {
        renderEditMessageButton(container, message);
    }

    responsesElem.appendChild(container);
}

/**
 * Validate user message
 */
function validateUserMessage(userMessage) {
    if (!userMessage || isStreaming) {
        console.log('Empty message or assistant is streaming');
        return false;
    }
    return true;
}

/**
 * Send user message to the server and render the response
 */
async function sendUserMessage() {

    try {

        await isLoggedInOrRedirect();

        const userMessage = messageElem.value.trim();
        if (!validateUserMessage(userMessage)) {
            return;
        }

        // Save as dialog if it's the first message
        let message = { role: 'user', content: userMessage };

        // Create new dialog if there are no messages
        if (currentDialogMessages.length === 0) {
            currentDialogID = await createDialog(userMessage);
        }

        // Push user message to current dialog messages
        currentDialogMessages.push(message);

        // Save user message and get the message ID
        const userMessageId = await createMessage(currentDialogID, message);

        // Clear the input field
        messageElem.value = '';

        renderStaticUserMessage(userMessage, userMessageId);

        // Scroll so that last user message is visible
        scrollToLastMessage();


        await renderAssistantMessage(message);
    } catch (error) {
        await logError(error, 'Error in sendUserMessage');
        console.error("Error in sendUserMessage:", error);
        Flash.setMessage('An error occurred. Please try again.', 'error');
    }
}

/**
 * Render static assistant message (without streaming)
 */
async function renderStaticAssistantMessage(message, messageId = null) {
    const { container, contentElement } = createMessageElement('Assistant', messageId);
    responsesElem.appendChild(container);

    // Render copy message
    renderCopyMessageButton(container, message);
    renderSteamedResponseText(contentElement, message);

    await addCopyButtons(contentElement, config);
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
    // Replace '\\' with '\cr'
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

            // preProcess: (text) => {
            //     console.log(text)
            //     return text
            // }

        });
    }
}

/**
 * Render streamed response text into the content element
 */
async function renderSteamedResponseText(contentElement, streamedResponseText) {
    const startTime = performance.now();

    streamedResponseText = modifyStreamedText(streamedResponseText);
    contentElement.innerHTML = mdNoHTML.render(streamedResponseText);

    // Optimize highlightCodeInElement. And katex rendering
    highlightCodeInElement(contentElement);
    renderKatex(contentElement);

    const endTime = performance.now();
    const timeSpent = endTime - startTime;
    console.log(`Time spent: ${timeSpent} milliseconds`);
}

let lastExecutionTime = 0;
let pendingExecution = false;
let executionInterval = 20


async function updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, force = false) {
    const currentTime = performance.now();

    if (!force && currentTime - lastExecutionTime < executionInterval) {
        if (!pendingExecution) {
            pendingExecution = true;
            setTimeout(async () => {
                pendingExecution = false;
                await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText);
            }, executionInterval - (currentTime - lastExecutionTime));
        }
        return;
    }

    lastExecutionTime = currentTime;

    renderSteamedResponseText(hiddenContentElem, streamedResponseText);

    try {
        const diff = dd.diff(contentElement, hiddenContentElem);
        if (diff.length) dd.apply(contentElement, diff);
    } catch (error) {
        console.log("Error in diffDOMExec:", error);
    }
}

/**
 * Render assistant message with streaming
 */
async function renderAssistantMessage() {

    // Create container for assistant message and content element
    const { container, contentElement, loader } = createMessageElement('Assistant');
    responsesElem.appendChild(container);

    //  Show loader
    loader.classList.remove('hidden');

    // Set streaming flag to true and disable buttons
    isStreaming = true;
    sendButtonElem.setAttribute('disabled', true);
    newButtonElem.setAttribute('disabled', true);

    // Reset streamed response text, create hidden content element, and get selected model
    let streamedResponseText = '';
    const hiddenContentElem = document.createElement('div');

    hiddenContentElem.classList.add('content');
    contentElement.classList.add('content');

    const selectModel = selectModelElem.value;

    // Stream processing function
    const processStream = async (reader, decoder) => {
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                // hide the loader on first payload
                loader.classList.add('hidden');

                // Each decoded chunk may contain several SSE lines
                decoder.decode(value, { stream: true })
                    .split('\n')
                    .filter(Boolean)   // remove empty lines
                    .forEach(processChunk);
            }
        } catch (error) {
            loader.classList.add('hidden');
            handleStreamError(error);
        }
    };

    // Function to handle chunk processing
    let reasoningActive = false; // Track if reasoning is currently open

    const processChunk = async rawLine => {
        // strip leading "data:" (if still there) and white-space
        const line = rawLine.replace(/^data:\s*/, '').trim();

        // End-of-stream marker – just finish normally
        if (line === '[DONE]') {
            // Close reasoning if still open
            if (reasoningActive) {
                streamedResponseText += ' </thinking>\n\n';
                reasoningActive = false;
            }
            await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, true);
            return;
        }

        // Skip anything that is not valid JSON *without* killing the stream
        let data;
        try {
            data = JSON.parse(line);
        } catch (_) {
            console.warn('Skipping non-JSON chunk:', line);
            return;
        }

        // Normal OpenAI streaming payload
        const delta = data.choices?.[0]?.delta ?? {};
        const finishReason = data.choices?.[0]?.finish_reason;

        // Handle reasoning tag logic
        if (delta.reasoning) {
            if (!reasoningActive) {
                streamedResponseText += '<thinking>\n';
                reasoningActive = true;
            }
            streamedResponseText += delta.reasoning;
        } else if (reasoningActive) {
            streamedResponseText += ' </thinking>\n\n';
            reasoningActive = false;
        }

        if (delta.content) streamedResponseText += delta.content;

        await updateContentDiff(
            contentElement,
            hiddenContentElem,
            streamedResponseText,
            Boolean(finishReason)        // force final diff when finish_reason is set
        );
    };

    // Error handling for stream
    const handleStreamError = (error) => {
        if (error.name === 'AbortError') {
            Flash.setMessage('Request was aborted', 'notice');
            console.log('Request was aborted');
        } else {
            console.error("Error in processStream:", error);
            Flash.setMessage('An error occurred while processing the stream.', 'error');
        }
    };

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: selectModel, messages: currentDialogMessages }),
            signal: controller.signal,
        });

        if (!response.ok) {
            throw new Error(`Server returned error: ${response.status} ${response.statusText}`);
        }
        if (!response.body) {
            throw new Error("Response body is empty. Try again later.");
        }

        // Allow aborting
        abortButtonElem.removeAttribute('disabled');

        // Process the stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        await processStream(reader, decoder);


    } catch (error) {
        loader.classList.add('hidden');
        console.error("Error in renderAssistantMessage:", error);

        Flash.setMessage('An error occurred. Please try again.', 'error');
    } finally {

        clearStreaming();

        // wait for the next frame to render
        // This is a workaround to ensure that the DOM is updated before executing the next code
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

        await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, true);

        // Enable buttons
        await addCopyButtons(contentElement, config);

        // Save message to the dialog
        let assistantMessage = { role: 'assistant', content: streamedResponseText };
        const assistantMessageId = await createMessage(currentDialogID, assistantMessage);
        
        // Store the message ID in the container
        container.setAttribute('data-message-id', assistantMessageId);

        // Render copy message
        renderCopyMessageButton(container, streamedResponseText);
        currentDialogMessages.push(assistantMessage);
    }
}


function scrollToLastMessage() {
    responsesElem.scrollTo({
        top: responsesElem.scrollHeight,
        behavior: 'smooth'
    });

}

let userInteracting = false;
let interactionTimeout;

// Listen for wheel on window
window.addEventListener('wheel', () => {
    userInteracting = true;
    scrollToBottom.style.display = 'none';
    clearTimeout(interactionTimeout);
    interactionTimeout = setTimeout(() => {
        userInteracting = false;
        checkScroll();
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
        checkScroll();
    }, 1000);
});

function checkScroll() {
    const threshold = 2; // px tolerance
    const atBottom = Math.abs(responsesElem.scrollHeight - responsesElem.scrollTop - responsesElem.clientHeight) <= threshold;
    const hasScrollbar = responsesElem.scrollHeight > responsesElem.clientHeight;

    if (hasScrollbar && !atBottom && !userInteracting) {
        scrollToBottom.style.display = 'flex';
    } else {
        scrollToBottom.style.display = 'none';
    }
}

// Listen for scrolls and content changes
responsesElem.addEventListener('scroll', checkScroll);
new MutationObserver(checkScroll).observe(responsesElem, { childList: true, subtree: true });

/**
 * Load a saved conversation
 */
async function loadDialog(savedMessages) {

    currentDialogMessages = savedMessages.slice();
    responsesElem.innerHTML = '';

    for (const msg of currentDialogMessages) {
        if (msg.role === 'user') {
            const message = msg.content;
            const messageId = msg.message_id;
            renderStaticUserMessage(message, messageId);
        } else {
            const message = msg.content;
            const messageId = msg.message_id;
            await renderStaticAssistantMessage(message, messageId);
        }
    }
}

/**
 * Initialize the dialog
 */
async function initializeDialog(dialogID) {
    try {
        let allMessages = await getMessages(dialogID);
        console.log('All messages:', allMessages);
        await loadDialog(allMessages);
    } catch (error) {
        console.error("Error in initializeDialog:", error);
        Flash.setMessage('An error occurred. Please try again.', 'error');
    }
}

async function initializeFromPrompt(promptID) {
    console.log('Initializing from prompt ID:', promptID);

    try {
        const response = await fetch(`/prompt/${promptID}/json`);
        if (!response.ok) {
            throw new Error(`Failed to fetch prompt: ${response.status} ${response.statusText}`);
        }

        const promptData = await response.json();
        console.log('Prompt data:', promptData);
        const promptText = promptData.prompt.prompt;

        // Render the prompt text as a user message
        renderStaticUserMessage(promptText);

        // Create a new dialog with the prompt text
        currentDialogID = await createDialog(promptText);

        // Save the prompt message to the dialog
        const promptMessage = { role: 'user', content: promptText };
        await createMessage(currentDialogID, promptMessage);

        currentDialogMessages.push({ role: 'user', content: promptText });
        console.log('Current dialog ID after prompt:', currentDialogMessages);

    } catch (error) {
        console.error("Error in initializeFromPrompt:", error);
        Flash.setMessage('An error occurred while initializing from prompt.', 'error');
    }
}

/**
 * Get the dialog ID from the URL and load the conversation
 * This only happens on page load
 */
const url = new URL(window.location.href);
const dialogID = url.pathname.split('/').pop();
if (dialogID) {

    currentDialogID = dialogID;
    loadingSpinner.classList.remove('hidden');

    console.log('Current dialog ID:', currentDialogID);
    await initializeDialog(currentDialogID);

    loadingSpinner.classList.add('hidden');
}

const promptID = url.searchParams.get('id');
if (promptID) {
    await initializeFromPrompt(promptID);
}