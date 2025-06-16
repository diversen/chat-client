import { Flash } from '/static/js/flash.js';
import { mdNoHTML } from '/static/js/markdown.js';
import { createDialog, getMessages, createMessage, getConfig, isLoggedInOrRedirect } from '/static/js/app-dialog.js';
import { responsesElem, messageElem, sendButtonElem, newButtonElem, abortButtonElem, selectModelElem, loadingSpinner, scrollToBottom } from '/static/js/app-elements.js';
import { } from '/static/js/app-events.js';
import { addCopyButtons } from '/static/js/app-copy-buttons.js';
import { logError } from '/static/js/error-log.js';
import { dd } from '/static/js/diff-dom.js';
import { modifyStreamedText } from '/static/js/utils.js';
import { copyIcon, checkIcon, generatingIcon } from '/static/js/app-icons.js';

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
    if (e.key === 'Enter' && e.shiftKey) {
        // Allow line break with Shift+Enter
        return;
    } else if (e.key === 'Enter') {
        e.preventDefault();
        await sendUserMessage();
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

function createMessageElement(role) {
    const containerClass = `${role.toLowerCase()}-message`;
    const messageContainer = document.createElement('div');
    messageContainer.classList.add(containerClass);

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
        // Trim the message to avoid copying extra whitespace
        message = message.trim();
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
 * Render user message to the DOM
 */
function renderStaticUserMessage(message) {
    const { container, contentElement } = createMessageElement('User');

    contentElement.style.whiteSpace = 'pre-wrap';
    contentElement.innerText = message;

    // Render copy message
    renderCopyMessageButton(container, message);

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

        // Save user message and push to all messages
        await createMessage(currentDialogID, message);

        // Clear the input field
        messageElem.value = '';

        renderStaticUserMessage(userMessage);

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
async function renderStaticAssistantMessage(message) {
    const { container, contentElement } = createMessageElement('Assistant');
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
    const processChunk = async rawLine => {
        // strip leading "data:" (if still there) and white-space
        const line = rawLine.replace(/^data:\s*/, '').trim();

        // End-of-stream marker – just finish normally
        if (line === '[DONE]') {
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
        await createMessage(currentDialogID, assistantMessage);

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
            renderStaticUserMessage(message);
        } else {
            const message = msg.content;
            await renderStaticAssistantMessage(message, 'Assistant');
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

async function initializeFromPrompt(promtpID) {
    console.log('Initializing from prompt ID:', promtpID);

    try {
        const response = await fetch(`/prompt/${promtpID}/json`);
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

const promtpID = url.searchParams.get('id');
if (promtpID) {
    await initializeFromPrompt(promtpID);
}