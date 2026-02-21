import {
    responsesElem,
    messageElem,
    sendButtonElem,
    newButtonElem,
    abortButtonElem,
    selectModelElem,
    imagePreviewModalElem,
    imagePreviewModalImageElem,
} from './app-elements.js';
import { addCopyButtons } from './app-copy-buttons.js';
import { copyIcon, checkIcon, editIcon } from './app-icons.js';

const ANCHOR_SPACER_CLASS = 'responses-anchor-spacer';

function getOrCreateAnchorSpacer() {
    let spacer = responsesElem.querySelector(`.${ANCHOR_SPACER_CLASS}`);
    if (!spacer) {
        spacer = document.createElement('div');
        spacer.className = ANCHOR_SPACER_CLASS;
        spacer.setAttribute('aria-hidden', 'true');
        responsesElem.appendChild(spacer);
    }
    return spacer;
}

function appendBeforeAnchorSpacer(element) {
    const spacer = getOrCreateAnchorSpacer();
    responsesElem.insertBefore(element, spacer);
}

function ensureScrollRoomForMessage(container, navOffset) {
    const targetTop = container.getBoundingClientRect().top + window.scrollY - navOffset;
    const targetScrollY = Math.max(0, targetTop);
    const doc = document.documentElement;
    const maxScrollY = Math.max(0, doc.scrollHeight - window.innerHeight);
    const extraScrollNeeded = Math.max(0, targetScrollY - maxScrollY);
    const spacer = getOrCreateAnchorSpacer();
    spacer.style.height = `${Math.ceil(extraScrollNeeded)}px`;
    return targetScrollY;
}

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
    messageActions.querySelector('.copy-message').addEventListener('click', (e) => {
        e.preventDefault();
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

function renderEditMessageButton(container, onEdit) {
    const messageActions = container.querySelector('.message-actions');

    const editButton = document.createElement('a');
    editButton.href = '#';
    editButton.className = 'edit-message';
    editButton.title = 'Edit message';
    editButton.innerHTML = editIcon;
    messageActions.appendChild(editButton);

    editButton.addEventListener('click', (e) => {
        e.preventDefault();
        const contentElement = container.querySelector('.content');
        const currentMessage = contentElement ? contentElement.innerText : '';
        showEditForm(container, currentMessage, onEdit);
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

function openImagePreviewModal(dataUrl, name) {
    if (!imagePreviewModalElem || !imagePreviewModalImageElem) return;
    imagePreviewModalImageElem.src = dataUrl;
    imagePreviewModalImageElem.alt = name || 'Selected image preview';
    imagePreviewModalElem.classList.remove('hidden');
}

function createMessageImages(images = []) {
    if (!Array.isArray(images) || images.length === 0) return null;

    const preview = document.createElement('div');
    preview.className = 'image-preview';

    images.forEach((image, index) => {
        const dataUrl = String(image?.data_url || '').trim();
        if (!dataUrl.startsWith('data:image/')) return;

        const item = document.createElement('div');
        item.className = 'image-preview-item';

        const thumbnail = document.createElement('img');
        thumbnail.className = 'image-preview-thumb';
        thumbnail.alt = `Message image ${index + 1}`;
        thumbnail.src = dataUrl;
        thumbnail.addEventListener('click', () => {
            openImagePreviewModal(dataUrl, thumbnail.alt);
        });

        item.appendChild(thumbnail);
        preview.appendChild(item);
    });

    if (preview.children.length === 0) return null;
    return preview;
}

function createChatView({ config, renderStreamedResponseText, updateContentDiff }) {
    return {
        renderStaticUserMessage(message, messageId = null, onEdit, images = []) {
            const { container, contentElement } = createMessageElement('User', messageId);
            const imagePreview = createMessageImages(images);
            if (imagePreview) {
                contentElement.insertAdjacentElement('beforebegin', imagePreview);
            }
            contentElement.style.whiteSpace = 'pre-wrap';
            contentElement.innerText = message;
            renderCopyMessageButton(container, message);

            if (messageId) {
                renderEditMessageButton(container, onEdit);
            }
            appendBeforeAnchorSpacer(container);
            return container;
        },
        async renderStaticAssistantMessage(message, messageId = null) {
            const { container, contentElement } = createMessageElement('Assistant', messageId);
            appendBeforeAnchorSpacer(container);
            renderCopyMessageButton(container, message);
            await renderStreamedResponseText(contentElement, message);
            await addCopyButtons(contentElement, config);
        },
        renderStaticToolMessage(toolMessage, beforeElement = null) {
            const { container, contentElement } = createMessageElement('Tool');
            const toolName = String(toolMessage?.tool_name || 'unknown_tool');
            const toolCallId = String(toolMessage?.tool_call_id || '');
            const argumentsJson = String(toolMessage?.arguments_json || '{}');
            const resultContent = String(toolMessage?.content || '');
            const errorText = String(toolMessage?.error_text || '');

            const details = document.createElement('details');
            details.className = 'tool-call-details';
            details.open = false;

            const summary = document.createElement('summary');
            summary.textContent = `MCP tool: ${toolName}`;
            details.appendChild(summary);

            const metadata = document.createElement('div');
            metadata.className = 'tool-call-meta';

            const callId = document.createElement('p');
            callId.innerHTML = '<strong>Call ID:</strong> ';
            callId.append(toolCallId);
            metadata.appendChild(callId);

            const argsLabel = document.createElement('p');
            argsLabel.innerHTML = '<strong>Arguments:</strong>';
            metadata.appendChild(argsLabel);

            const argsPre = document.createElement('pre');
            argsPre.textContent = argumentsJson;
            metadata.appendChild(argsPre);

            const resultLabel = document.createElement('p');
            resultLabel.innerHTML = `<strong>${errorText ? 'Error' : 'Result'}:</strong>`;
            metadata.appendChild(resultLabel);

            const resultPre = document.createElement('pre');
            resultPre.textContent = errorText || resultContent;
            metadata.appendChild(resultPre);

            details.appendChild(metadata);
            contentElement.appendChild(details);

            if (beforeElement && beforeElement.parentNode === responsesElem) {
                responsesElem.insertBefore(container, beforeElement);
            } else {
                appendBeforeAnchorSpacer(container);
            }
            return container;
        },
        createAssistantContainer() {
            const { container, contentElement, loader } = createMessageElement('Assistant');
            appendBeforeAnchorSpacer(container);
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
            const topBar = document.querySelector('.top-bar');
            const navOffset = topBar ? topBar.getBoundingClientRect().height : 80;
            const targetScrollY = ensureScrollRoomForMessage(container, navOffset);
            window.scrollTo({ top: targetScrollY, behavior: 'auto' });
        },
        scrollToLastMessage() {
            window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
        },
    };
}

export { createChatView };
