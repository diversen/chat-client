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
import { Flash } from './flash.js';
import { copyIcon, checkIcon, editIcon } from './app-icons.js';
import { mdNoHTML } from './markdown.js';
import { openImagePreviewModal } from './image-preview-modal.js';

const ANCHOR_SPACER_CLASS = 'responses-anchor-spacer';
const MIN_ANCHOR_SPACER_HEIGHT_PX = 20;
const EXTRA_STREAMING_SLACK_PX = 100;
const MESSAGE_INPUT_MIN_HEIGHT_PX = 60;
const MESSAGE_INPUT_MAX_VIEWPORT_HEIGHT_RATIO = 0.25;

function resizeMessageInput() {
    if (!messageElem) return;

    const maxHeightPx = Math.max(
        MESSAGE_INPUT_MIN_HEIGHT_PX,
        Math.floor(window.innerHeight * MESSAGE_INPUT_MAX_VIEWPORT_HEIGHT_RATIO),
    );

    messageElem.style.height = 'auto';
    messageElem.style.height = `${Math.min(messageElem.scrollHeight, maxHeightPx)}px`;
    messageElem.style.overflowY = messageElem.scrollHeight > maxHeightPx ? 'auto' : 'hidden';
}

function resetMessageInputHeight() {
    if (!messageElem) return;
    messageElem.style.height = `${MESSAGE_INPUT_MIN_HEIGHT_PX}px`;
    messageElem.style.overflowY = 'hidden';
}

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
    setAnchorSpacerHeight(requiredSpacerHeight + EXTRA_STREAMING_SLACK_PX, false);
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
            Flash.setMessage('Message content cannot be empty', 'error');
            return;
        }
        const messageId = container.getAttribute('data-message-id');
        if (!messageId) {
            Flash.setMessage('Cannot edit message: message ID not found', 'error');
            return;
        }
        try {
            sendButton.disabled = true;
            sendButton.textContent = 'Sending...';
            await onEdit(messageId, newContent, container);
        } catch (error) {
            console.error('Error updating message:', error);
            Flash.setMessage('Error updating message. Please try again.', 'error');
            sendButton.disabled = false;
            sendButton.textContent = 'Send';
        }
    });
}

function createMessageImages(images = []) {
    if (!Array.isArray(images) || images.length === 0) return null;

    const preview = document.createElement('div');
    preview.className = 'image-preview';

    images.forEach((image, index) => {
        const dataUrl = String(image?.data_url || '').trim();
        if (!dataUrl.startsWith('data:image/')) return;

        const item = document.createElement('div');
        item.className = 'upload-preview-tile message-image-tile';

        const tileButton = document.createElement('button');
        tileButton.type = 'button';
        tileButton.className = 'upload-preview-open';
        tileButton.title = `Preview attached image ${index + 1}`;
        tileButton.setAttribute('aria-label', `Preview attached image ${index + 1}`);
        tileButton.addEventListener('click', () => {
            openImagePreviewModal(imagePreviewModalElem, imagePreviewModalImageElem, dataUrl, tileButton.title);
        });

        const thumbnail = document.createElement('img');
        thumbnail.className = 'message-image-thumb';
        thumbnail.alt = `Message image ${index + 1}`;
        thumbnail.src = dataUrl;

        tileButton.appendChild(thumbnail);
        item.appendChild(tileButton);
        preview.appendChild(item);
    });

    if (preview.children.length === 0) return null;
    return preview;
}

function formatAttachmentSize(sizeBytes) {
    const size = Number(sizeBytes || 0);
    if (!Number.isFinite(size) || size <= 0) return '';
    if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)}MB`;
    if (size >= 1024) return `${Math.round(size / 1024)}KB`;
    return `${size}B`;
}

function createMessageAttachments(attachments = [], removable = false, onRemove = null) {
    if (!Array.isArray(attachments) || attachments.length === 0) return null;

    const preview = document.createElement('div');
    preview.className = 'attachment-preview';

    attachments.forEach((attachment) => {
        const attachmentId = String(attachment?.attachment_id || attachment?.id || '');
        const fileName = String(attachment?.name || 'attachment');
        const fileExtension = (fileName.split('.').pop() || 'file').slice(0, 6).toUpperCase();
        const item = document.createElement('div');
        item.className = 'upload-preview-tile message-attachment-tile';

        const tileButton = document.createElement(attachmentId ? 'button' : 'div');
        if (attachmentId) {
            tileButton.type = 'button';
            tileButton.title = `Preview ${fileName}`;
            tileButton.setAttribute('aria-label', `Preview ${fileName}`);
            tileButton.addEventListener('click', () => {
                window.open(`/chat/attachment/${attachmentId}/preview`, '_blank', 'noopener');
            });
        }
        tileButton.className = 'upload-preview-open';

        const meta = document.createElement('div');
        meta.className = 'upload-preview-meta';

        const kind = document.createElement('span');
        kind.className = 'upload-preview-kind';
        kind.textContent = fileExtension;
        meta.appendChild(kind);

        const name = document.createElement('span');
        name.className = 'upload-preview-name';
        name.textContent = fileName;
        meta.appendChild(name);

        const sizeText = formatAttachmentSize(attachment?.size_bytes || attachment?.size);
        if (sizeText) {
            const size = document.createElement('span');
            size.className = 'upload-preview-size';
            size.textContent = sizeText;
            meta.appendChild(size);
        }

        tileButton.appendChild(meta);
        item.appendChild(tileButton);

        if (removable) {
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'image-preview-remove';
            remove.textContent = '×';
            remove.setAttribute('aria-label', `Remove ${name.textContent}`);
            remove.addEventListener('click', () => {
                if (typeof onRemove === 'function') {
                    onRemove(attachmentId);
                }
            });
            item.appendChild(remove);
        }

        preview.appendChild(item);
    });

    return preview.children.length ? preview : null;
}

function tryParseJson(value) {
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    if (!trimmed) return null;
    try {
        return JSON.parse(trimmed);
    } catch (_) {
        return null;
    }
}

function appendLabeledPre(container, label, value, preClassName = '') {
    const labelElement = document.createElement('p');
    labelElement.innerHTML = `<strong>${label}:</strong>`;
    container.appendChild(labelElement);

    const pre = document.createElement('pre');
    if (preClassName) {
        pre.classList.add(preClassName);
    }
    pre.textContent = value;
    container.appendChild(pre);
}

function appendLabeledMarkdownCode(container, label, language, code) {
    const labelElement = document.createElement('p');
    labelElement.innerHTML = `<strong>${label}:</strong>`;
    container.appendChild(labelElement);

    const block = document.createElement('div');
    block.innerHTML = mdNoHTML.render(`\`\`\`${language}\n${code}\n\`\`\``);

    if (typeof hljs !== 'undefined') {
        const codeBlocks = block.querySelectorAll('pre code');
        codeBlocks.forEach((element) => {
            hljs.highlightElement(element);
        });
    }
    addCopyButtons(block);
    container.appendChild(block);
}

function appendMarkdownCode(container, language, code, withCopyButton = false) {
    const block = document.createElement('div');
    block.innerHTML = mdNoHTML.render(`\`\`\`${language}\n${code}\n\`\`\``);

    if (typeof hljs !== 'undefined') {
        const codeBlocks = block.querySelectorAll('pre code');
        codeBlocks.forEach((element) => {
            hljs.highlightElement(element);
        });
    }
    if (withCopyButton) {
        addCopyButtons(block);
    }
    container.appendChild(block);
}

function appendLabeledMarkdownBlock(container, label, language, code, withCopyButton = false) {
    const labelElement = document.createElement('p');
    labelElement.innerHTML = `<strong>${label}:</strong>`;
    container.appendChild(labelElement);
    appendMarkdownCode(container, language, code, withCopyButton);
}

function isPythonLikeToolName(toolName) {
    const normalized = String(toolName || '').trim().toLowerCase();
    if (!normalized) return false;
    return normalized === 'python' || normalized.includes('python');
}

function renderDefaultToolCallMeta(metadata, payload) {
    appendLabeledPre(metadata, 'Arguments', payload.argumentsJson);
    appendLabeledPre(metadata, payload.errorText ? 'Error' : 'Result', payload.errorText || payload.resultContent);
}

function renderPythonToolCallMeta(metadata, payload) {
    const parsedArgs = tryParseJson(payload.argumentsJson);
    const pythonCode = typeof parsedArgs?.code === 'string' ? parsedArgs.code : '';

    if (pythonCode) {
        appendLabeledMarkdownBlock(metadata, 'Code', 'python', pythonCode, true);
    } else {
        appendLabeledPre(metadata, 'Arguments', payload.argumentsJson);
    }

    if (payload.errorText) {
        appendLabeledPre(metadata, 'Error', payload.errorText);
        return;
    }

    const parsedResult = tryParseJson(payload.resultContent);
    if (parsedResult !== null) {
        appendMarkdownCode(metadata, 'json', JSON.stringify(parsedResult, null, 2));
        return;
    }

    appendLabeledPre(metadata, 'Result', payload.resultContent, 'tool-call-result');
}

const TOOL_META_RENDERERS = {
    python: renderPythonToolCallMeta,
    default: renderDefaultToolCallMeta,
};

function bindToggleControl(toggleElement, bodyElement, label = '') {
    if (!toggleElement || !bodyElement) return;

    if (label) {
        toggleElement.title = `Show/hide ${label} details`;
    }

    const toggle = () => {
        const isOpen = !bodyElement.classList.contains('hidden');
        bodyElement.classList.toggle('hidden', isOpen);
        toggleElement.setAttribute('aria-expanded', String(!isOpen));
    };

    toggleElement.addEventListener('click', toggle);
    toggleElement.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggle();
        }
    });
}

function populateToolCallBody(container, toolMessage, toolCallsOpenByDefault, roleElement) {
    const toolName = String(toolMessage?.tool_name || 'unknown_tool');
    const argumentsJson = String(toolMessage?.arguments_json || '{}');
    const resultContent = String(toolMessage?.content || '');
    const errorText = String(toolMessage?.error_text || '');
    const toolBody = document.createElement('div');
    toolBody.className = toolCallsOpenByDefault ? 'tool-call-body' : 'tool-call-body hidden';
    container.appendChild(toolBody);

    if (roleElement) {
        roleElement.classList.add('tool-toggle');
        roleElement.setAttribute('role', 'button');
        roleElement.setAttribute('tabindex', '0');
        roleElement.setAttribute('aria-expanded', String(toolCallsOpenByDefault));
        bindToggleControl(roleElement, toolBody, toolName);
    }

    const renderer = isPythonLikeToolName(toolName)
        ? renderPythonToolCallMeta
        : (TOOL_META_RENDERERS[toolName] || TOOL_META_RENDERERS.default);
    renderer(toolBody, {
        toolName,
        argumentsJson,
        resultContent,
        errorText,
    });

    return toolBody;
}

function createToolMessageContainer(toolMessage, toolCallsOpenByDefault) {
    const { container, contentElement } = createMessageElement('Tool');
    const roleElement = container.querySelector('.role_tool');
    populateToolCallBody(contentElement, toolMessage, toolCallsOpenByDefault, roleElement);

    return container;
}

function createEmbeddedToolCallElement(toolMessage, toolCallsOpenByDefault) {
    const container = document.createElement('section');
    container.className = 'assistant-tool-call';
    populateToolCallBody(container, toolMessage, toolCallsOpenByDefault, null);
    return container;
}

function splitThinkingMarkup(rawText) {
    const text = String(rawText || '');
    const tagRegex = /<\/?(?:think|thinking|thought)>/gi;
    const segments = [];
    let isThinking = false;
    let lastIndex = 0;
    let match;

    const pushSegment = (type, value) => {
        if (!value) return;
        const previous = segments[segments.length - 1];
        if (previous && previous.type === type) {
            previous.text += value;
            return;
        }
        segments.push({ type, text: value });
    };

    while ((match = tagRegex.exec(text)) !== null) {
        pushSegment(isThinking ? 'thinking' : 'normal', text.slice(lastIndex, match.index));
        isThinking = !String(match[0] || '').startsWith('</');
        lastIndex = tagRegex.lastIndex;
    }

    pushSegment(isThinking ? 'thinking' : 'normal', text.slice(lastIndex));
    return segments;
}

function createAssistantSegmentShell(messageId = null, initialKind = 'Thinking', showLoader = false) {
    const container = document.createElement('section');
    container.className = 'assistant-segment';
    if (messageId) {
        container.setAttribute('data-message-id', String(messageId));
    }

    const segmentHeader = document.createElement('div');
    segmentHeader.className = 'assistant-segment-header';
    const segmentStep = document.createElement('span');
    segmentStep.className = 'assistant-segment-step';
    segmentStep.textContent = 'Step';
    const segmentKindElement = document.createElement('span');
    segmentKindElement.className = 'assistant-segment-kind';
    segmentKindElement.textContent = String(initialKind || 'Thinking');
    const loader = document.createElement('div');
    loader.className = 'loading-model';
    if (!showLoader) {
        loader.classList.add('hidden');
    }
    const statusElement = document.createElement('span');
    statusElement.className = 'assistant-status hidden';
    segmentHeader.appendChild(segmentStep);
    segmentHeader.appendChild(segmentKindElement);
    segmentHeader.appendChild(loader);
    segmentHeader.appendChild(statusElement);
    container.appendChild(segmentHeader);

    const contentElement = document.createElement('div');
    contentElement.className = 'content';
    container.appendChild(contentElement);

    const bodyElement = document.createElement('div');
    bodyElement.className = 'assistant-segment-body';
    contentElement.appendChild(bodyElement);

    const actionsElement = document.createElement('div');
    actionsElement.className = 'message-actions hidden';
    actionsElement.innerHTML = `
      <a href="#" class="copy-message" title="Copy message to clipboard">
        ${copyIcon}
      </a>
    `;
    contentElement.appendChild(actionsElement);

    return {
        container,
        segmentHeader,
        loader,
        statusElement,
        setSegmentIndex(index) {
            const safeIndex = Number(index);
            segmentStep.textContent = Number.isFinite(safeIndex) && safeIndex > 0 ? `Step ${safeIndex}` : 'Step';
        },
        setStepVisible(isVisible) {
            segmentStep.classList.toggle('hidden', !isVisible);
        },
        setSegmentKind(kind) {
            const safeKind = String(kind || '').trim();
            segmentKindElement.textContent = safeKind || 'Thinking';
        },
        setLoading(isLoading) {
            loader.classList.toggle('hidden', !isLoading);
        },
        setStatus(text) {
            const safeText = String(text || '').trim();
            statusElement.textContent = safeText;
            statusElement.classList.toggle('hidden', !safeText);
        },
        clearStatus() {
            statusElement.textContent = '';
            statusElement.classList.add('hidden');
        },
        setCollapsible(isOpen = false) {
            segmentHeader.classList.add('assistant-segment-toggle');
            segmentHeader.setAttribute('role', 'button');
            segmentHeader.setAttribute('tabindex', '0');
            segmentHeader.setAttribute('aria-expanded', String(Boolean(isOpen)));
            segmentHeader.title = `Show/hide ${String(initialKind || 'segment').toLowerCase()} details`;
        },
        contentElement: bodyElement,
        contentWrapperElement: contentElement,
        actionsElement,
    };
}

function createChatView({ config, renderStreamedResponseText, updateContentDiff }) {
    const toolCallsOpenByDefault = false;
    const getSegmentKindKey = (kind) => String(kind || '').toLowerCase();
    const getSegmentBehavior = (kind) => {
        const segmentKind = getSegmentKindKey(kind);
        return {
            kind: segmentKind,
            isCollapsible: segmentKind === 'thinking' || segmentKind === 'tool',
            defaultOpen: segmentKind === 'tool'
                    ? toolCallsOpenByDefault
                    : false,
        };
    };
    const setupCollapsibleSegment = (segment, bodyElement, kind, openState) => {
        const behavior = getSegmentBehavior(kind);
        if (!behavior.isCollapsible || !bodyElement) {
            return null;
        }

        segment.setCollapsible(openState);
        const syncVisibility = () => {
            const isExpanded = String(segment.segmentHeader.getAttribute('aria-expanded') || '').toLowerCase() === 'true';
            bodyElement.classList.toggle('hidden', !isExpanded);
        };
        syncVisibility();
        bindToggleControl(segment.segmentHeader, bodyElement, behavior.kind);
        return {
            behavior,
            syncVisibility,
        };
    };
    const resolveSegmentOpenState = (behavior, openState) => (
        typeof openState === 'boolean' ? openState : behavior.defaultOpen
    );
    const appendCommittedTextSegment = async (
        parentElement,
        {
            kind,
            text,
            messageId = null,
            stepIndex,
            openState,
        },
    ) => {
        const safeText = String(text || '');
        if (!safeText.trim()) return null;
        const segment = createAssistantSegmentShell(messageId, kind, false);
        const behavior = getSegmentBehavior(kind);
        segment.setSegmentIndex(stepIndex);
        parentElement.appendChild(segment.container);
        await renderStreamedResponseText(segment.contentElement, safeText);
        if (behavior.isCollapsible) {
            setupCollapsibleSegment(
                segment,
                segment.contentWrapperElement,
                behavior.kind,
                resolveSegmentOpenState(behavior, openState),
            );
        }
        if (behavior.kind === 'answer') {
            renderCopyMessageButton(segment.container, safeText);
            await addCopyButtons(segment.contentElement, config);
        }
        return segment;
    };
    const appendCommittedToolSegment = (
        parentElement,
        {
            toolPayload,
            stepIndex,
            openState,
        },
    ) => {
        const segment = createAssistantSegmentShell(null, 'Tool', false);
        const behavior = getSegmentBehavior('tool');
        segment.setSegmentIndex(stepIndex);
        parentElement.appendChild(segment.container);
        const toolElement = createEmbeddedToolCallElement(
            toolPayload,
            resolveSegmentOpenState(behavior, openState),
        );
        setupCollapsibleSegment(
            segment,
            toolElement.querySelector('.tool-call-body'),
            behavior.kind,
            resolveSegmentOpenState(behavior, openState),
        );
        segment.contentElement.appendChild(toolElement);
        return segment;
    };

    resetMessageInputHeight();
    window.addEventListener('resize', resizeMessageInput);

    return {
        createMessageAttachments,
        renderStaticUserMessage(message, messageId = null, onEdit, images = [], attachments = [], displayRole = 'User') {
            const safeDisplayRole = String(displayRole || 'User');
            const { container, contentElement } = createMessageElement(safeDisplayRole, messageId, 'User');
            const imagePreview = createMessageImages(images);
            if (imagePreview) {
                contentElement.insertAdjacentElement('beforebegin', imagePreview);
            }
            const attachmentPreview = createMessageAttachments(attachments);
            if (attachmentPreview) {
                contentElement.insertAdjacentElement('beforebegin', attachmentPreview);
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
        async renderStaticAssistantTurn(turnMessages = [], beforeElement = null, options = {}) {
            const { container: turnContainer, contentElement: turnContentElement } = createMessageElement('Assistant');
            turnContainer.classList.add('assistant-turn');
            const segmentOpenStates = Array.isArray(options?.segmentOpenStates) ? options.segmentOpenStates : [];
            let segmentStateIndex = 0;
            if (beforeElement && beforeElement.parentNode === responsesElem) {
                responsesElem.insertBefore(turnContainer, beforeElement);
            } else {
                appendBeforeAnchorSpacer(turnContainer);
            }

            let segmentIndex = 0;
            const nextStepIndex = () => {
                segmentIndex += 1;
                return segmentIndex;
            };
            const nextSegmentOpenState = () => {
                const openState = segmentOpenStates[segmentStateIndex];
                segmentStateIndex += 1;
                return openState;
            };

            for (const item of turnMessages) {
                const isTool = item?.role === 'tool' || item?.event_type === 'tool_call';
                if (isTool) {
                    const toolPayload = item?.event_type === 'tool_call'
                        ? {
                            tool_call_id: String(item?.tool_call_id || ''),
                            tool_name: String(item?.tool_name || ''),
                            arguments_json: String(item?.arguments_json || '{}'),
                            content: String(item?.result_text || ''),
                            error_text: String(item?.error_text || ''),
                        }
                        : item;
                    appendCommittedToolSegment(turnContentElement, {
                        toolPayload,
                        stepIndex: nextStepIndex(),
                        openState: nextSegmentOpenState(),
                    });
                    continue;
                }

                const isAssistantSegment = item && (
                    item.role === 'assistant' || item.event_type === 'assistant_segment'
                );
                if (!isAssistantSegment) {
                    continue;
                }

                let reasoningText = '';
                let contentText = '';
                if (item?.event_type === 'assistant_segment') {
                    reasoningText = String(item?.reasoning_text || '');
                    contentText = String(item?.content_text || '');
                } else {
                    const parts = splitThinkingMarkup(String(item?.content || ''));
                    for (const part of parts) {
                        if (part.type === 'thinking') reasoningText += part.text;
                        else contentText += part.text;
                    }
                }

                const hasReasoning = String(reasoningText || '').trim().length > 0;
                await appendCommittedTextSegment(turnContentElement, {
                    kind: 'Thinking',
                    text: reasoningText,
                    messageId: item?.message_id || null,
                    stepIndex: hasReasoning ? nextStepIndex() : segmentIndex + 1,
                    openState: hasReasoning ? nextSegmentOpenState() : undefined,
                });
                const hasContent = String(contentText || '').trim().length > 0;
                await appendCommittedTextSegment(turnContentElement, {
                    kind: 'Answer',
                    text: contentText,
                    messageId: item?.message_id || null,
                    stepIndex: hasContent ? nextStepIndex() : segmentIndex + 1,
                });
            }

            if (!turnContentElement.children.length) {
                turnContainer.remove();
                return null;
            }
            return turnContainer;
        },
        renderStaticToolMessage(toolMessage, beforeElement = null) {
            const container = createToolMessageContainer(toolMessage, toolCallsOpenByDefault);

            if (beforeElement && beforeElement.parentNode === responsesElem) {
                responsesElem.insertBefore(container, beforeElement);
            } else {
                appendBeforeAnchorSpacer(container);
            }
            return container;
        },
        createAssistantTurn() {
            const beforeBaseScrollHeight = getBaseScrollHeight();
            const { container: turnContainer, contentElement: turnContentElement } = createMessageElement('Assistant');
            turnContainer.classList.add('assistant-turn');
            appendBeforeAnchorSpacer(turnContainer);
            const afterBaseScrollHeight = getBaseScrollHeight();
            const consumedOnInsert = Math.max(0, afterBaseScrollHeight - beforeBaseScrollHeight);
            consumeAnchorSpacerBy(consumedOnInsert, false);
            let lastBaseScrollHeight = getBaseScrollHeight();
            let segmentIndex = 0;

            const createTextSegment = (kind, showLoader = false, options = {}) => {
                const segment = createAssistantSegmentShell(null, kind, showLoader);
                const behavior = getSegmentBehavior(kind);
                const isTransient = Boolean(options.transient);
                if (Boolean(options.hideStep)) {
                    segment.setStepVisible(false);
                }
                if (!isTransient) {
                    segmentIndex += 1;
                    segment.setSegmentIndex(segmentIndex);
                }
                const collapsibleState = setupCollapsibleSegment(
                    segment,
                    segment.contentWrapperElement,
                    behavior.kind,
                    behavior.defaultOpen,
                );
                if (behavior.isCollapsible && !collapsibleState) {
                    throw new Error(`Expected collapsible state for segment kind: ${behavior.kind}`);
                }

                const hiddenContentElem = document.createElement('div');
                hiddenContentElem.classList.add('content');
                let streamedResponseText = '';
                let pendingRender = false;
                let pendingForceRender = false;
                let renderInFlight = false;
                let renderPromise = Promise.resolve();

                const syncScrollAfterRender = (beforeBaseScrollHeight) => {
                    const afterBaseScrollHeight = getBaseScrollHeight();
                    const consumedHeight = Math.max(0, afterBaseScrollHeight - beforeBaseScrollHeight);
                    consumeAnchorSpacerBy(consumedHeight, false);
                    lastBaseScrollHeight = afterBaseScrollHeight;
                };

                const flushPendingRender = () => {
                    if (renderInFlight) {
                        return renderPromise;
                    }

                    renderInFlight = true;
                    renderPromise = (async () => {
                        try {
                            while (pendingRender || pendingForceRender) {
                                const force = pendingForceRender;
                                pendingRender = false;
                                pendingForceRender = false;
                                const beforeBaseScrollHeight = lastBaseScrollHeight;
                                await updateContentDiff(segment.contentElement, hiddenContentElem, streamedResponseText, force);
                                collapsibleState?.syncVisibility();
                                syncScrollAfterRender(beforeBaseScrollHeight);
                            }
                        } finally {
                            renderInFlight = false;
                        }
                    })();

                    return renderPromise;
                };

                return {
                    ...segment,
                    segmentKind: kind.toLowerCase(),
                    async appendText(text, force = false) {
                        streamedResponseText += text;
                        if (force) {
                            pendingForceRender = true;
                            await flushPendingRender();
                            return;
                        }
                        pendingRender = true;
                        void flushPendingRender();
                    },
                    async finalize() {
                        pendingForceRender = true;
                        await flushPendingRender();
                        return {
                            kind: kind.toLowerCase(),
                            text: streamedResponseText,
                            isVisible: streamedResponseText.trim().length > 0,
                        };
                    },
                };
            };

            let activeAssistantSegment = null;

            return {
                container: turnContainer,
                ensureAssistantSegment(kind = 'Thinking', options = {}) {
                    if (activeAssistantSegment && activeAssistantSegment.segmentKind === String(kind || '').toLowerCase()) {
                        return activeAssistantSegment;
                    }
                    if (activeAssistantSegment) return null;
                    const beforeBaseScrollHeight = getBaseScrollHeight();
                    activeAssistantSegment = createTextSegment(kind, Boolean(options.showLoader), options);
                    turnContentElement.appendChild(activeAssistantSegment.container);
                    const afterBaseScrollHeight = getBaseScrollHeight();
                    const consumedOnInsert = Math.max(0, afterBaseScrollHeight - beforeBaseScrollHeight);
                    consumeAnchorSpacerBy(consumedOnInsert, false);
                    lastBaseScrollHeight = afterBaseScrollHeight;
                    return activeAssistantSegment;
                },
                getActiveAssistantSegment() {
                    return activeAssistantSegment;
                },
                async finalizeAssistantSegment() {
                    if (!activeAssistantSegment) return null;
                    activeAssistantSegment.setLoading(false);
                    activeAssistantSegment.clearStatus();
                    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                    const finalized = await activeAssistantSegment.finalize();
                    const segment = activeAssistantSegment;
                    if (segment.segmentKind === 'answer') {
                        renderCopyMessageButton(segment.container, finalized.text);
                        await addCopyButtons(segment.contentElement, config);
                    }
                    activeAssistantSegment = null;
                    return {
                        ...finalized,
                        container: segment.container,
                        contentElement: segment.contentElement,
                    };
                },
                appendToolCall(toolMessage) {
                    const beforeBaseScrollHeight = getBaseScrollHeight();
                    segmentIndex += 1;
                    const targetSegment = appendCommittedToolSegment(turnContentElement, {
                        toolPayload: toolMessage,
                        stepIndex: segmentIndex,
                    });
                    const afterBaseScrollHeight = getBaseScrollHeight();
                    const consumedOnInsert = Math.max(0, afterBaseScrollHeight - beforeBaseScrollHeight);
                    consumeAnchorSpacerBy(consumedOnInsert, false);
                    lastBaseScrollHeight = afterBaseScrollHeight;
                    return targetSegment;
                },
                removeIfEmpty() {
                    if (!turnContentElement.children.length) {
                        turnContainer.remove();
                    }
                },
            };
        },
        clearInput() {
            messageElem.value = '';
            resetMessageInputHeight();
        },
        resizeInput() { resizeMessageInput(); },
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
