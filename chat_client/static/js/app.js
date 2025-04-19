import { Flash } from '/static/js/flash.js';
import { mdNoHTML } from '/static/js/markdown.js';
import { createDialog, getMessages, createMessage, getConfig, isLoggedInOrRedirect } from '/static/js/app-dialog.js';
import { responsesElem, messageElem, sendButtonElem, newButtonElem, abortButtonElem, selectModelElem, loadingSpinner, scrollToBottom } from '/static/js/app-elements.js';
import { } from '/static/js/app-events.js';
import { addCopyButtons } from '/static/js/app-copy-buttons.js';
import { logError } from '/static/js/error-log.js';
import { dd } from '/static/js/diff-dom.js';
import { modifySteamedText } from '/static/js/utils.js';
import { copyIcon, checkIcon, generatingIcon } from '/static/js/app-icons.js';

const config = await getConfig();

// Math rendering
const useKatex = config.use_katex;

// Regarding scrolling
let isScrolling = false;
function getIsScrolling() {
    if (isScrolling) {
        return true;
    }
    return false;
}

function setIsScrolling(value) {
    isScrolling = value;
}

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
            // If Ctrl+Enter is pressed, add a new line
            messageElem.value += '\n';
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

    streamedResponseText = modifySteamedText(streamedResponseText);
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
let executionInterval = 10


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

    // setIsScrolling(true);
    // Stream processing function
    const processStream = async (reader, decoder) => {
        try {

            while (true) {

                const { done, value } = await reader.read();

                // If loader is not hidden, hide it
                if (!loader.classList.contains('hidden')) {
                    loader.classList.toggle('hidden');
                }

                if (done) break;
                const decoded = decoder.decode(value, { stream: true });
                let dataElems = decoded.split('data: ');

                // Remove empty elements form the array
                dataElems = dataElems.filter((data) => data.trim() !== '');
                dataElems.forEach(await processChunk);
            }
        } catch (error) {
            loader.classList.add('hidden');
            handleStreamError(error);
        }
    };

    // Function to handle chunk processing
    let totalTokenCount = 0;
    const processChunk = async (dataPart) => {

        try {

            const data = JSON.parse(dataPart);
            const messagePart = data.choices[0].delta.content;
            const finishReason = data.choices[0].finish_reason
            const error = data.error;

            if (error) {
                throw new Error(error);
            }

            totalTokenCount += 1;

            if (!finishReason) {
                streamedResponseText += messagePart;
            }

            if (totalTokenCount % 1 === 0) {
                await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText);
            }

            if (finishReason) {
                await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, true);
            }
        } catch (error) {
            console.log("Error in processChunk:", error);
            controller.abort();
        }
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

    // if (getIsScrolling()) {
        responsesElem.scrollTo({
            top: responsesElem.scrollHeight,
            behavior: 'smooth'
        });
    // }
}

/**
 * Scroll to the bottom of the responses element
 * If mutation observer is triggered, scroll to the bottom
 */
// const observer = new MutationObserver((mutationList, observer) => {
//     const lastAssistantMessage = responsesElem.querySelector('.assistant-message:last-child');
//     if (lastAssistantMessage) {
//         const distance = lastAssistantMessage.getBoundingClientRect().top - responsesElem.getBoundingClientRect().top;
//         if (distance < 40) {
//             setIsScrolling(false);
//         }
//     }

//     for (const mutation of mutationList) {
//         if (mutation.type === "childList") {
//             if (mutation.removedNodes.length > 0) {
//                 return;
//             }
//         }

//         if (mutation.type === "characterData") {
//             // return;
//         }
//         if (mutation.type === "subtree") {
//             return;
//         }

//         scrollToLastMessage();

//     }
// });

// const observer = new MutationObserver(() => {
//     requestAnimationFrame(() => {
//         const threshold = 40;
//         const distanceToBottom = responsesElem.scrollHeight - responsesElem.scrollTop - responsesElem.clientHeight;

//         if (distanceToBottom <= threshold) {
//             setIsScrolling(false);
//         }

//         scrollToLastMessage();
//     });
// });

// observer.observe(responsesElem, {
//     childList: true,
//     subtree: true,
//     characterData: true,
//     // attributes: true,
// });


function checkScroll() {
    const threshold = 2; // px tolerance for floating-point errors
    const atBottom = Math.abs(responsesElem.scrollHeight - responsesElem.scrollTop - responsesElem.clientHeight) <= threshold;
    const hasScrollbar = responsesElem.scrollHeight > responsesElem.clientHeight;
  
    if (hasScrollbar && !atBottom && !getIsScrolling()) {
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