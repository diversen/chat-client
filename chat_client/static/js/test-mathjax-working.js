import { Flash } from '/static/js/flash.js';
import { getMarkdownIt } from '/static/js/markdown-it.js';


const md = getMarkdownIt();

let isScrolling = false; // Reponse should scroll to the bottom is true
let isStreaming = false;
let intervalID;

// Array to store all messages
const allMessages = [];

// Elements
const responsesElem = document.getElementById('responses');
const messageElem = document.getElementById('message');
const sendButtonElem = document.getElementById('send');
const newButtonElem = document.getElementById('new');
const messageFormElem = document.getElementById('message-form');
const abortButtonElem = document.getElementById('abort');
const loadingSpinnerElem = document.getElementById('loading-spinner');
const promptElem = document.querySelector('.prompt');

// Focus on the message input when the page loads
messageElem.focus();

// Add event listener to the send button
sendButtonElem.addEventListener('click', async () => {
    await sendUserMessage();
});

let controller = new AbortController();

function clearSteaming() {
    console.log('Clearing streaming');
    clearInterval(intervalID);
    isStreaming = false;
    abortButtonElem.setAttribute('disabled', true);
}

// Add event listner to the textarea. isScrolling indicates if text is being generated
// and is scrolling to the bottom. The user can scroll up to stop the auto-scrolling.
responsesElem.addEventListener('wheel', (event) => {

    // Check on event if scrolling is up
    if (event.deltaY < 0) {
        console.log('Whell up to go up in messages');
        isScrolling = false;
    }

    // Check on event if scrolling is down
    if (event.deltaY > 0) {

        // Set scolling to true if the bottom of messagesElem is close to promptElem
        if (responsesElem.scrollTop + responsesElem.clientHeight >= responsesElem.scrollHeight - 200) {
            isScrolling = true;
        }
    }
}, { passive: true });

let startY = 0;

document.addEventListener('touchstart', (event) => {
    startY = event.touches[0].clientY;
}, { passive: true });

document.addEventListener('touchmove', (event) => {
    let deltaY = event.touches[0].clientY - startY;

    if (deltaY > -10) { // Adjust threshold if needed
        console.log('Swiping down to go up in messages');
        isScrolling = false;
    }

    if (deltaY < 10) { // Adjust threshold if needed
        if (responsesElem.scrollTop + responsesElem.clientHeight >= responsesElem.scrollHeight - 200) {
            console.log('Swiping up to go down in messages and auto-scroll again');
            isScrolling = true;
        }
    }
}, { passive: true });


abortButtonElem.addEventListener('click', () => {
    console.log('Aborting request');
    controller.abort();
    controller = new AbortController();
});

newButtonElem.addEventListener('click', () => {
    console.log('New conversation');
    if (intervalID) {
        clearInterval(intervalID);
    }
    window.location.reload();
});

// Shortcut to send message when user presses Enter + Ctrl
messageElem.addEventListener('keyup', async (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
        await sendUserMessage();
    }
});


async function sendUserMessage() {
    const userMessage = messageElem.value.trim();
    if (!userMessage || isStreaming) {
        console.log('Empty message or assistant is streaming');
        return;
    }

    if (userMessage) {
        const message = { role: 'user', content: userMessage };
        messageElem.value = '';

        // This fixes the issue of empty prompt on page load
        promptElem.style.bottom = '40px';
        promptElem.style.top = 'unset';
        promptElem.style.transform = 'unset';

        try {
            renderUserMessage(userMessage, 'User');
            isScrolling = true;
            await renderAssistantMessage(message);
        } catch (error) {
            console.error("Error in sendUserMessage: ", error);
            Flash.setMessage('An error occurred. Please try again.', 'error');
        } finally {

        }
    }
}

function renderUserMessage(message, role) {
    const userMessageElem = document.createElement("div");
    userMessageElem.classList.add('user-message');

    const roleElem = document.createElement("p");
    roleElem.classList.add('role');
    roleElem.textContent = role;

    userMessageElem.appendChild(roleElem);

    const contentElem = document.createElement("div");
    contentElem.classList.add('content');
    contentElem.style.whiteSpace = 'pre-wrap';
    contentElem.textContent = message;

    userMessageElem.appendChild(contentElem);
    responsesElem.appendChild(userMessageElem);
}


async function renderAssistantMessage(message) {

    // disable the sendButtonElem
    isStreaming = true;

    allMessages.push(message);

    // Create assistant message elements and append to the DOM
    const assistantResponseElem = document.createElement("div");
    assistantResponseElem.classList.add('assistant-message');

    responsesElem.appendChild(assistantResponseElem);

    const roleElem = document.createElement("p");
    roleElem.classList.add('role');

    // Create content element to store the role and content
    const contentElem = document.createElement("div");
    contentElem.classList.add('content');

    // Create hidden content element to store the markdown content
    const hiddenContentElem = document.createElement("div");

    assistantResponseElem.appendChild(roleElem);
    assistantResponseElem.appendChild(contentElem);

    let responseText = '';
    let isFirstResponsePart = true;


    function highlightCodeInElement(element) {
        const codeBlocks = element.querySelectorAll('pre code');
        codeBlocks.forEach(hljs.highlightElement);
    }

    // Helper function: Capitalize role text
    function capitalizeRole(role) {
        return role.charAt(0).toUpperCase() + role.slice(1);
    }

    // Send a POST request to start the chat stream
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: allMessages }),
            signal: controller.signal,
        });

        if (!response.ok) {
            throw new Error(`Server returned error: ${response.status} ${response.statusText}`);
        }

        if (!response.body) {
            throw new Error("Response body is empty. Try again later.");
        }

        // Enable abort button
        abortButtonElem.removeAttribute('disabled');

        // Set an interval to update markdown rendering
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        // Process streaming response
        async function processStream() {
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        break;
                    }

                    let chunk = decoder.decode(value, { stream: true });
                    chunk.split('data: ').forEach(dataPart => processChunk(dataPart));
                }
            } catch (error) {
                clearSteaming();
                if (error.name === 'AbortError') {
                    Flash.setMessage('Request was aborted', 'success');
                    console.log('Request was aborted');
                } else {
                    console.error("Error in processStream:", error);
                    Flash.setMessage('An error occurred while processing the stream.', 'error');
                }


            }
        }

        let tokenCount = 0;

        // Helper function: Process each chunk of data
        function processChunk(dataPart) {
            if (!dataPart.trim()) return;
            const parsedData = JSON.parse(dataPart.trim());

            if (isFirstResponsePart) {
                roleElem.textContent = capitalizeRole(parsedData.message.role);
                isFirstResponsePart = false;
            }

            contentElem.innerHTML += parsedData.message.content;
            tokenCount += 1;
            if (isScrolling && tokenCount % 10 == 0) {
                tokenCount = 0;
                scrollToBottom();
            }

            // Finalize response if streaming is complete
            if (parsedData.done === true) {
                finalizeResponse();
                clearSteaming();
                scrollToBottom();
            }
        }

        // Helper function: Finalize updates when response is complete
        function finalizeResponse() {

            renderMathInElement(contentElem, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '\\(', right: '\\)', display: false },
                    { left: '\\[', right: '\\]', display: true },
                    { left: '\\begin{equation}', right: '\\end{equation}', display: true },
                    { left: '$', right: '$', display: false }
                ]
            });
                
        
            contentElem.innerHTML = md.render(contentElem.innerHTML);    
            
            highlightCodeInElement(contentElem);
            addCopyButtons(contentElem);
            console.log(responseText)
        }

        await processStream();

        // Store the complete response when finished
        allMessages.push({ role: 'assistant', content: responseText });

    } catch (error) {
        console.error("Error in renderAssistantMessage: ", error);
        clearSteaming();

        // Store the incomplete response
        allMessages.push({ role: 'assistant', content: responseText });
        Flash.setMessage('An error occurred. Please try again.', 'error');
    }
}

function addCopyButtons(assistantResponseElem) {
    const codeBlocks = assistantResponseElem.querySelectorAll('pre code');

    // Get 'content' element and add 'copy-button-container' and 'copy-button' elements
    const contentElem = assistantResponseElem.querySelector('.content');
    codeBlocks.forEach(code => {

        const button = document.createElement("button");
        button.classList.add('copy-button');
        button.textContent = "Copy code";
        button.onclick = function () {
            navigator.clipboard.writeText(code.textContent).then(() => {
                button.textContent = "Copied!";

                setTimeout(() => {
                    button.textContent = "Copy code";
                }, 2000);

            }, err => {
                console.log('Failed to copy: ', err);
            });
        };

        // Wrap button in div and insert before code block
        const buttonContainer = document.createElement('div');
        buttonContainer.classList.add('copy-button-container');
        buttonContainer.appendChild(button);

        const parent = code.parentNode; // 'pre' element
        parent.insertBefore(buttonContainer, code);
    });
}

function scrollToBottom() {
    if (isScrolling) {
        responsesElem.scrollTop = responsesElem.scrollHeight;
    }
}
