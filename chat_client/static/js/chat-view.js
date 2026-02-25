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
const MIN_ANCHOR_SPACER_HEIGHT_PX = 20;

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
    const currentSpacerHeight = getAnchorSpacerHeight();
    const targetTop = container.getBoundingClientRect().top + window.scrollY - navOffset;
    const targetScrollY = Math.max(0, targetTop);
    const doc = document.documentElement;
    // Compute max scroll without the existing spacer so we don't collapse
    // spacer room that is still required for top alignment.
    const baseScrollHeight = Math.max(0, doc.scrollHeight - currentSpacerHeight);
    // Keep this unclamped: when content is shorter than viewport, the negative
    // delta tells us exactly how much spacer is needed to make top alignment possible.
    const baseScrollDelta = baseScrollHeight - window.innerHeight;
    const requiredSpacerHeight = Math.max(0, targetScrollY - baseScrollDelta);
    setAnchorSpacerHeight(requiredSpacerHeight, false);
    return targetScrollY;
}

function getAnchorSpacerHeight() {
    const spacer = getOrCreateAnchorSpacer();
    const inlineHeight = parseFloat(spacer.style.height);
    if (Number.isFinite(inlineHeight)) {
        return Math.max(0, inlineHeight);
    }
    const computedHeight = parseFloat(window.getComputedStyle(spacer).height);
    return Number.isFinite(computedHeight) ? Math.max(0, computedHeight) : 0;
}

function setAnchorSpacerHeight(heightPx, animate = false) {
    const spacer = getOrCreateAnchorSpacer();
    spacer.style.transition = animate ? 'height 180ms ease-out' : 'none';
    spacer.style.height = `${Math.max(MIN_ANCHOR_SPACER_HEIGHT_PX, Math.ceil(heightPx))}px`;
}

function getBaseScrollHeight() {
    const doc = document.documentElement;
    return Math.max(0, doc.scrollHeight - getAnchorSpacerHeight());
}

function consumeAnchorSpacerBy(usedHeightPx, animate = false) {
    if (!Number.isFinite(usedHeightPx) || usedHeightPx <= 0) return;
    const current = getAnchorSpacerHeight();
    if (current <= 0) return;
    setAnchorSpacerHeight(Math.max(MIN_ANCHOR_SPACER_HEIGHT_PX, current - usedHeightPx), animate);
}

function createMessageElement(role, messageId = null, containerRole = null) {
    const resolvedContainerRole = (containerRole || role).toLowerCase();
    const containerClass = `${resolvedContainerRole}-message`;
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
        renderStaticUserMessage(message, messageId = null, onEdit, images = [], displayRole = 'User') {
            const safeDisplayRole = String(displayRole || 'User');
            const { container, contentElement } = createMessageElement(safeDisplayRole, messageId, 'User');
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
            const beforeBaseScrollHeight = getBaseScrollHeight();
            appendBeforeAnchorSpacer(container);
            const afterBaseScrollHeight = getBaseScrollHeight();
            const consumedOnInsert = Math.max(0, afterBaseScrollHeight - beforeBaseScrollHeight);
            consumeAnchorSpacerBy(consumedOnInsert, false);
            loader.classList.remove('hidden');

            const hiddenContentElem = document.createElement('div');
            hiddenContentElem.classList.add('content');
            contentElement.classList.add('content');

            let streamedResponseText = '';
            let reasoningActive = false;
            let lastBaseScrollHeight = getBaseScrollHeight();

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
                    const beforeBaseScrollHeight = lastBaseScrollHeight;
                    await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, force);
                    const afterBaseScrollHeight = getBaseScrollHeight();
                    const consumedHeight = Math.max(0, afterBaseScrollHeight - beforeBaseScrollHeight);
                    consumeAnchorSpacerBy(consumedHeight, false);
                    lastBaseScrollHeight = afterBaseScrollHeight;
                },
                async finalize() {
                    this.closeReasoningIfOpen();
                    const beforeBaseScrollHeight = lastBaseScrollHeight;
                    await updateContentDiff(contentElement, hiddenContentElem, streamedResponseText, true);
                    const afterBaseScrollHeight = getBaseScrollHeight();
                    const consumedHeight = Math.max(0, afterBaseScrollHeight - beforeBaseScrollHeight);
                    consumeAnchorSpacerBy(consumedHeight, false);
                    lastBaseScrollHeight = afterBaseScrollHeight;
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
        async scrollMessageToTop(container) {
            if (!container) return;

            const getNavOffset = () => {
                const topBar = document.querySelector('.top-bar');
                return topBar ? topBar.getBoundingClientRect().height : 80;
            };

            const align = () => {
                if (!container.isConnected) return;
                const navOffset = getNavOffset();
                ensureScrollRoomForMessage(container, navOffset);
                container.style.scrollMarginTop = `${Math.ceil(navOffset)}px`;
                container.scrollIntoView({ block: 'start', inline: 'nearest', behavior: 'smooth' });
            };

            const isAligned = () => {
                if (!container.isConnected) return true;
                const navOffset = getNavOffset();
                const top = container.getBoundingClientRect().top;
                return Math.abs(top - navOffset) <= 2;
            };

            // Wait for stable alignment before returning.
            let attemptsRemaining = 12;
            while (attemptsRemaining > 0) {
                align();
                await new Promise((resolve) => requestAnimationFrame(resolve));
                if (isAligned()) break;
                attemptsRemaining -= 1;
            }
        },
        scrollToLastMessage() {
            window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
        },
    };
}

export { createChatView };
