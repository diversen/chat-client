import {
    responsesElem,
    messageElem,
    sendButtonElem,
    newButtonElem,
    abortButtonElem,
    selectModelElem,
} from './app-elements.js';
import { addCopyButtons } from './app-copy-buttons.js';
import { copyIcon, checkIcon, editIcon } from './app-icons.js';

function createMessageElement(role, messageId = null) {
    const containerClass = `${role.toLowerCase()}-message`;
    const messageContainer = document.createElement('div');
    messageContainer.classList.add(containerClass);

    if (messageId) {
        messageContainer.setAttribute('data-message-id', messageId);
    }

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

    const loaderSpan = messageContainer.querySelector('.loading-model');
    const contentElement = messageContainer.querySelector('.content');
    return { container: messageContainer, contentElement: contentElement, loader: loaderSpan };
}

function renderCopyMessageButton(container, message) {
    const messageActions = container.querySelector('.message-actions');
    messageActions.classList.remove('hidden');
    messageActions.querySelector('.copy-message').addEventListener('click', () => {
        navigator.clipboard.writeText(message);
        const copyButton = messageActions.querySelector('.copy-message');
        copyButton.innerHTML = checkIcon;
        setTimeout(() => {
            copyButton.innerHTML = copyIcon;
        }, 2000);
    });
}

function hideEditForm(container) {
    const contentElement = container.querySelector('.content');
    const messageActions = container.querySelector('.message-actions');
    const editForm = container.querySelector('.edit-form');

    if (editForm) {
        editForm.remove();
    }

    contentElement.style.display = '';
    messageActions.style.display = '';
}

function renderEditMessageButton(container, originalMessage, onEdit) {
    const messageActions = container.querySelector('.message-actions');

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

    contentElement.style.display = 'none';
    messageActions.style.display = 'none';

    const editForm = document.createElement('div');
    editForm.className = 'edit-form';
    editForm.innerHTML = `
    <textarea class="edit-textarea">${originalMessage}</textarea>
    <div class="edit-buttons">
      <button class="edit-cancel">Cancel</button>
      <button class="edit-send">Send</button>
    </div>
  `;

    contentElement.insertAdjacentElement('afterend', editForm);

    const textarea = editForm.querySelector('.edit-textarea');
    const cancelButton = editForm.querySelector('.edit-cancel');
    const sendButton = editForm.querySelector('.edit-send');

    textarea.focus();
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';

    cancelButton.addEventListener('click', () => {
        hideEditForm(container);
    });

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

function createChatView({ config, renderStreamedResponseText, updateContentDiff }) {
    return {
        renderStaticUserMessage(message, messageId = null, onEdit) {
            const { container, contentElement } = createMessageElement('User', messageId);
            contentElement.style.whiteSpace = 'pre-wrap';
            contentElement.innerText = message;
            renderCopyMessageButton(container, message);

            if (messageId) {
                renderEditMessageButton(container, message, onEdit);
            }
            responsesElem.appendChild(container);
            return container;
        },
        async renderStaticAssistantMessage(message, messageId = null) {
            const { container, contentElement } = createMessageElement('Assistant', messageId);
            responsesElem.appendChild(container);
            renderCopyMessageButton(container, message);
            await renderStreamedResponseText(contentElement, message);
            await addCopyButtons(contentElement, config);
        },
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
                },
            };
        },
        clearInput() { messageElem.value = ''; },
        disableSend() { sendButtonElem.setAttribute('disabled', true); },
        enableSend() { sendButtonElem.removeAttribute('disabled'); },
        disableNew() {
            if (!newButtonElem) return;
            newButtonElem.classList.add('is-disabled-link');
            newButtonElem.setAttribute('aria-disabled', 'true');
            newButtonElem.setAttribute('tabindex', '-1');
            if (document.activeElement === newButtonElem) {
                newButtonElem.blur();
            }
        },
        enableNew() {
            if (!newButtonElem) return;
            newButtonElem.classList.remove('is-disabled-link');
            newButtonElem.removeAttribute('aria-disabled');
            newButtonElem.removeAttribute('tabindex');
        },
        disableAbort() { abortButtonElem.setAttribute('disabled', true); },
        enableAbort() { abortButtonElem.removeAttribute('disabled'); },
        getSelectedModel() { return selectModelElem.value; },
        attachCopy(container, text) { renderCopyMessageButton(container, text); },
        hideEditForm(container) { hideEditForm(container); },
        scrollMessageToTop(container) {
            if (!container) return;
            const navOffset = 80;
            const targetTop = container.getBoundingClientRect().top + window.scrollY - navOffset;
            window.scrollTo({ top: Math.max(0, targetTop), behavior: 'auto' });
        },
        scrollToLastMessage() {
            window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
        },
    };
}

export { createChatView };
