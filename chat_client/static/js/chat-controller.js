import { Flash } from './flash.js';
import { logError } from './error-log.js';
import { addCopyButtons } from './app-copy-buttons.js';
import { Requests } from './requests.js';
import { openImagePreviewModal, closeImagePreviewModal } from './image-preview-modal.js';
import {
    responsesElem,
    messageElem,
    sendButtonElem,
    abortButtonElem,
    scrollToBottom,
    imageInputElem,
    pendingUploadsElem,
    attachImageButtonElem,
    attachmentInputElem,
    attachFileButtonElem,
    selectModelElem,
    imagePreviewModalElem,
    imagePreviewModalImageElem,
    imagePreviewModalCloseElem,
} from './app-elements.js';

const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024;

function fileToDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
        reader.readAsDataURL(file);
    });
}

function formatAttachmentSize(sizeBytes) {
    const size = Number(sizeBytes || 0);
    if (!Number.isFinite(size) || size <= 0) return '';
    if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)}MB`;
    if (size >= 1024) return `${Math.round(size / 1024)}KB`;
    return `${size}B`;
}

class ConversationController {
    constructor({ view, storage, auth, chat, config }) {
        this.view = view;
        this.storage = storage;
        this.auth = auth;
        this.chat = chat;
        this.config = config;
        this.isStreaming = false;
        this.messages = [];
        this.dialogId = null;
        this.abortController = new AbortController();
        this.pendingImages = [];
        this.pendingAttachments = [];

        this.wireUI();
        this.updateAttachmentUI();
        this.updateSendButtonState();
        this.renderPendingUploads();
    }

    setEditFormSubmissionEnabled(enabled) {
        const editSendButtons = responsesElem.querySelectorAll('.edit-form .edit-send');
        editSendButtons.forEach((button) => {
            button.disabled = !enabled;
        });
    }

    getSelectedModelCapabilities() {
        const selectedModel = this.view.getSelectedModel();
        const modelCapabilities = this.config?.model_capabilities;
        if (modelCapabilities && typeof modelCapabilities === 'object' && modelCapabilities[selectedModel]) {
            return modelCapabilities[selectedModel];
        }
        const visionModels = Array.isArray(this.config.vision_models) ? this.config.vision_models : [];
        return {
            supports_images: visionModels.includes(selectedModel),
            supports_attachments: true,
            supports_tools: false,
        };
    }

    selectedModelSupportsImages() {
        return Boolean(this.getSelectedModelCapabilities()?.supports_images);
    }

    selectedModelSupportsAttachments() {
        return Boolean(this.getSelectedModelCapabilities()?.supports_attachments);
    }

    updateAttachmentUI() {
        const supportsImages = this.selectedModelSupportsImages();
        const supportsAttachments = this.selectedModelSupportsAttachments();
        attachImageButtonElem.classList.toggle('hidden', !supportsImages);
        attachImageButtonElem.disabled = !supportsImages;
        imageInputElem.disabled = !supportsImages;
        attachFileButtonElem.classList.toggle('hidden', !supportsAttachments);
        attachFileButtonElem.disabled = !supportsAttachments;
        attachmentInputElem.disabled = !supportsAttachments;

        if (!supportsImages && this.pendingImages.length > 0) {
            this.clearPendingImages();
        }
        if (!supportsAttachments && this.pendingAttachments.length > 0) {
            this.clearPendingAttachments();
        }
    }

    updateSendButtonState() {
        const hasText = messageElem.value.trim().length > 0;
        const hasImages = this.selectedModelSupportsImages() && this.pendingImages.length > 0;
        const hasAttachments = this.selectedModelSupportsAttachments() && this.pendingAttachments.length > 0;
        const canSend = !this.isStreaming && (hasText || hasImages || hasAttachments);

        if (canSend) {
            this.view.enableSend();
        } else {
            this.view.disableSend();
        }
    }

    renderPendingUploads() {
        if (!this.pendingImages.length && !this.pendingAttachments.length) {
            pendingUploadsElem.innerHTML = '';
            pendingUploadsElem.classList.add('hidden');
            return;
        }

        pendingUploadsElem.classList.remove('hidden');
        pendingUploadsElem.innerHTML = '';

        const preview = document.createElement('div');
        preview.className = 'image-preview';

        this.pendingImages.forEach((img) => {
            const sizeText = formatAttachmentSize(img.size);
            const item = document.createElement('div');
            item.className = 'upload-preview-tile';

            const tileButton = document.createElement('button');
            tileButton.type = 'button';
            tileButton.className = 'upload-preview-open';
            tileButton.title = `Preview ${img.name}`;
            tileButton.setAttribute('aria-label', `Preview ${img.name}`);
            tileButton.addEventListener('click', () => {
                this.openImagePreviewModal(img.dataUrl, img.name);
            });

            const thumbnail = document.createElement('img');
            thumbnail.className = 'upload-preview-thumb';
            thumbnail.alt = img.name;
            thumbnail.src = img.dataUrl;

            const meta = document.createElement('div');
            meta.className = 'upload-preview-meta';

            const kindElement = document.createElement('span');
            kindElement.className = 'upload-preview-kind';
            kindElement.textContent = 'IMAGE';

            const nameElement = document.createElement('span');
            nameElement.className = 'upload-preview-name';
            nameElement.textContent = img.name;

            meta.appendChild(kindElement);
            meta.appendChild(nameElement);

            if (sizeText) {
                const sizeElement = document.createElement('span');
                sizeElement.className = 'upload-preview-size';
                sizeElement.textContent = sizeText;
                meta.appendChild(sizeElement);
            }

            tileButton.appendChild(thumbnail);
            tileButton.appendChild(meta);

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'image-preview-remove';
            remove.title = `Remove ${img.name}`;
            remove.setAttribute('aria-label', `Remove ${img.name}`);
            remove.textContent = '×';
            remove.addEventListener('click', () => {
                this.pendingImages = this.pendingImages.filter((pending) => pending.id !== img.id);
                this.renderPendingUploads();
                this.updateSendButtonState();
            });

            item.appendChild(tileButton);
            item.appendChild(remove);
            preview.appendChild(item);
        });

        this.pendingAttachments.forEach((attachment) => {
            const attachmentId = String(attachment?.attachment_id || '');
            const fileName = String(attachment?.name || 'attachment');
            const fileExtension = (fileName.split('.').pop() || 'file').slice(0, 6).toUpperCase();
            const sizeText = formatAttachmentSize(attachment?.size_bytes);
            const item = document.createElement('div');
            item.className = 'upload-preview-tile';

            const tileButton = document.createElement('button');
            tileButton.type = 'button';
            tileButton.className = 'upload-preview-open';
            tileButton.title = `Preview ${fileName}`;
            tileButton.setAttribute('aria-label', `Preview ${fileName}`);
            tileButton.addEventListener('click', () => {
                if (!attachmentId) return;
                window.open(`/chat/attachment/${attachmentId}/preview`, '_blank', 'noopener');
            });

            const extensionElement = document.createElement('span');
            extensionElement.className = 'upload-preview-kind';
            extensionElement.textContent = fileExtension;

            const nameElement = document.createElement('span');
            nameElement.className = 'upload-preview-name';
            nameElement.textContent = fileName;

            const meta = document.createElement('div');
            meta.className = 'upload-preview-meta';
            meta.appendChild(extensionElement);
            meta.appendChild(nameElement);

            if (sizeText) {
                const sizeElement = document.createElement('span');
                sizeElement.className = 'upload-preview-size';
                sizeElement.textContent = sizeText;
                meta.appendChild(sizeElement);
            }

            tileButton.appendChild(meta);

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'image-preview-remove';
            remove.title = `Remove ${fileName}`;
            remove.setAttribute('aria-label', `Remove ${fileName}`);
            remove.textContent = '×';
            remove.addEventListener('click', () => {
                this.pendingAttachments = this.pendingAttachments.filter(
                    (pending) => String(pending.attachment_id) !== attachmentId,
                );
                this.renderPendingUploads();
                this.updateSendButtonState();
            });

            item.appendChild(tileButton);
            item.appendChild(remove);
            preview.appendChild(item);
        });

        pendingUploadsElem.appendChild(preview);
    }

    openImagePreviewModal(dataUrl, name) {
        openImagePreviewModal(imagePreviewModalElem, imagePreviewModalImageElem, dataUrl, name);
    }

    closeImagePreviewModal() {
        closeImagePreviewModal(imagePreviewModalElem, imagePreviewModalImageElem);
    }

    clearPendingImages() {
        this.pendingImages = [];
        imageInputElem.value = '';
        this.closeImagePreviewModal();
        this.renderPendingUploads();
        this.updateSendButtonState();
    }

    clearPendingAttachments() {
        this.pendingAttachments = [];
        attachmentInputElem.value = '';
        this.renderPendingUploads();
        this.updateSendButtonState();
    }

    async handleImageSelection(files) {
        if (!this.selectedModelSupportsImages()) {
            this.clearPendingImages();
            imageInputElem.value = '';
            Flash.setMessage('The selected model does not support image inputs.', 'notice');
            return;
        }

        const selectedFiles = Array.from(files || []);
        if (!selectedFiles.length) return;

        const newImages = [];
        for (const file of selectedFiles) {
            if (!file.type.startsWith('image/')) {
                Flash.setMessage(`Skipped ${file.name}: file is not an image`, 'notice');
                continue;
            }
            if (file.size > MAX_IMAGE_SIZE_BYTES) {
                Flash.setMessage(`Skipped ${file.name}: file is larger than 10MB`, 'notice');
                continue;
            }
            try {
                const dataUrl = await fileToDataURL(file);
                newImages.push({
                    id: `${Date.now()}-${Math.random()}`,
                    name: file.name,
                    type: file.type,
                    size: file.size,
                    dataUrl,
                });
            } catch (error) {
                console.error('Error reading image:', error);
                Flash.setMessage(`Skipped ${file.name}: could not read file`, 'notice');
            }
        }

        this.pendingImages = this.pendingImages.concat(newImages);
        imageInputElem.value = '';
        this.renderPendingUploads();
        this.updateSendButtonState();
    }

    async handleAttachmentSelection(files) {
        if (!this.selectedModelSupportsAttachments()) {
            this.clearPendingAttachments();
            attachmentInputElem.value = '';
            Flash.setMessage('The selected model does not support file attachments.', 'notice');
            return;
        }

        const selectedFiles = Array.from(files || []);
        if (!selectedFiles.length) return;

        await this.auth.ensure();
        for (const file of selectedFiles) {
            try {
                const uploaded = await this.storage.uploadAttachment(file);
                this.pendingAttachments.push(uploaded);
            } catch (error) {
                console.error('Error uploading attachment:', error);
                Flash.setMessage(
                    Requests.getErrorMessage(error, `Skipped ${file.name}: could not upload file`),
                    'notice',
                );
            }
        }

        attachmentInputElem.value = '';
        this.renderPendingUploads();
        this.updateSendButtonState();
    }

    wireUI() {
        sendButtonElem.addEventListener('click', async () => {
            await this.sendUserMessage();
        });

        messageElem.addEventListener('input', () => {
            this.view.resizeInput();
            this.updateSendButtonState();
        });

        messageElem.addEventListener('focus', () => {
            const openEditForms = responsesElem.querySelectorAll('.edit-form');
            openEditForms.forEach((editForm) => {
                const container = editForm.closest('[data-message-id]');
                if (container) this.view.hideEditForm(container);
            });
            this.checkScroll();
        });

        attachImageButtonElem.addEventListener('click', () => {
            if (!this.selectedModelSupportsImages()) {
                Flash.setMessage('The selected model does not support image inputs.', 'notice');
                return;
            }
            imageInputElem.click();
        });

        attachFileButtonElem.addEventListener('click', () => {
            if (!this.selectedModelSupportsAttachments()) {
                Flash.setMessage('The selected model does not support file attachments.', 'notice');
                return;
            }
            attachmentInputElem.click();
        });

        if (selectModelElem) {
            selectModelElem.addEventListener('change', () => {
                this.updateAttachmentUI();
                this.updateSendButtonState();
            });
        }

        imageInputElem.addEventListener('change', async (event) => {
            await this.handleImageSelection(event.target.files);
        });

        attachmentInputElem.addEventListener('change', async (event) => {
            await this.handleAttachmentSelection(event.target.files);
        });

        if (imagePreviewModalCloseElem) {
            imagePreviewModalCloseElem.addEventListener('click', () => {
                this.closeImagePreviewModal();
            });
        }

        if (imagePreviewModalElem) {
            imagePreviewModalElem.addEventListener('click', (event) => {
                if (event.target === imagePreviewModalElem) {
                    this.closeImagePreviewModal();
                }
            });
        }

        window.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                this.closeImagePreviewModal();
            }
        });

        abortButtonElem.addEventListener('click', () => {
            this.abortController.abort();
            this.abortController = new AbortController();
        });

        messageElem.addEventListener('keydown', async (e) => {
            if (e.key !== 'Enter') return;
            if (e.ctrlKey) {
                e.preventDefault();
                const start = messageElem.selectionStart;
                const end = messageElem.selectionEnd;
                messageElem.value = messageElem.value.substring(0, start) + '\n' + messageElem.value.substring(end);
                messageElem.selectionStart = messageElem.selectionEnd = start + 1;
                this.view.resizeInput();
                this.updateSendButtonState();
                return;
            }
            e.preventDefault();
            await this.sendUserMessage();
        });

        let interactionTimeout;
        const checkScrollAfterInteraction = () => {
            clearTimeout(interactionTimeout);
            interactionTimeout = setTimeout(() => {
                this.checkScroll();
            }, 1000);
        };

        window.addEventListener('wheel', () => {
            checkScrollAfterInteraction();
        });

        window.addEventListener('touchstart', (event) => {
            if (scrollToBottom && event.target instanceof Element && event.target.closest('#scroll-to-bottom')) {
                return;
            }
            clearTimeout(interactionTimeout);
        });

        window.addEventListener('touchend', () => {
            checkScrollAfterInteraction();
        });

        window.addEventListener('scroll', () => this.checkScroll(), { passive: true });
        new MutationObserver(() => {
            this.checkScroll();
            if (this.isStreaming) this.setEditFormSubmissionEnabled(false);
        }).observe(responsesElem, { childList: true, subtree: true });
    }

    checkScroll() {
        if (!scrollToBottom) return;
        const isEditingMessage = Boolean(responsesElem.querySelector('.edit-form'));

        const doc = document.documentElement;
        const hasScrollbar = doc.scrollHeight > window.innerHeight;
        const distanceFromBottom = Math.max(0, doc.scrollHeight - (window.innerHeight + window.scrollY));
        const hideThreshold = 12;
        if (!hasScrollbar || isEditingMessage) {
            scrollToBottom.style.display = 'none';
            return;
        }

        if (distanceFromBottom <= hideThreshold) {
            scrollToBottom.style.display = 'none';
            return;
        }

        scrollToBottom.style.display = 'flex';
    }

    validateUserMessage(userMessage) {
        const hasImages = this.selectedModelSupportsImages() && this.pendingImages.length > 0;
        const hasAttachments = this.selectedModelSupportsAttachments() && this.pendingAttachments.length > 0;
        return !!(this.isStreaming === false && (userMessage || hasImages || hasAttachments));
    }

    getInitialPromptRole() {
        const selectedModel = this.view.getSelectedModel();
        const systemMessageModels = Array.isArray(this.config.system_message_models) ? this.config.system_message_models : [];
        return systemMessageModels.includes(selectedModel) ? 'system' : 'user';
    }

    createTurnId() {
        if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
            return globalThis.crypto.randomUUID();
        }
        return `turn-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    async sendUserMessage() {
        try {
            await this.auth.ensure();
            const userMessage = messageElem.value.trim();
            const images = this.selectedModelSupportsImages()
                ? this.pendingImages.map((img) => ({ data_url: img.dataUrl }))
                : [];
            const attachments = this.selectedModelSupportsAttachments()
                ? this.pendingAttachments.map((attachment) => ({
                    attachment_id: attachment.attachment_id,
                    name: attachment.name,
                    content_type: attachment.content_type,
                    size_bytes: attachment.size_bytes,
                }))
                : [];
            if (!this.validateUserMessage(userMessage)) return;
            const message = { role: 'user', content: userMessage, images: images, attachments };
            const attachmentSummary = attachments.length
                ? `${attachments.length} file${attachments.length > 1 ? 's' : ''}`
                : '';
            const imageSummary = images.length
                ? `${images.length} image${images.length > 1 ? 's' : ''}`
                : '';
            const summaryParts = [imageSummary, attachmentSummary].filter(Boolean);
            const messageTextForStorage = userMessage || `[${summaryParts.join(', ')} attached]`;

            if (!this.dialogId) {
                const title = userMessage || (summaryParts.length ? `Attachment message (${summaryParts.join(', ')})` : 'New chat');
                this.dialogId = await this.storage.createDialog(title);

                // If this chat started from a custom prompt, persist that prompt
                // as the first message only when the user sends their first addition.
                if (this.messages.length > 0) {
                    for (const priorMessage of this.messages) {
                        if (priorMessage.role !== 'user' && priorMessage.role !== 'system') continue;
                        await this.storage.createMessage(this.dialogId, {
                            role: priorMessage.role,
                            content: priorMessage.content,
                            images: priorMessage.images || [],
                            attachments: priorMessage.attachments || [],
                        });
                    }
                }
            }

            const userMessageId = await this.storage.createMessage(this.dialogId, {
                role: 'user',
                content: messageTextForStorage,
                model: this.view.getSelectedModel(),
                images,
                attachments,
            });

            this.messages.push({ ...message, message_id: userMessageId });

            this.view.clearInput();
            this.clearPendingImages();
            this.clearPendingAttachments();

            const userContainer = this.view.renderStaticUserMessage(
                messageTextForStorage,
                userMessageId,
                async (id, newContent, container) => {
                    await this.handleMessageUpdate(id, newContent, container);
                },
                images,
                attachments,
            );

            await this.view.scrollMessageToTop(userContainer);

            await this.renderAssistantMessage();
        } catch (error) {
            await logError(error, 'Error in sendUserMessage');
            console.error('Error in sendUserMessage:', error);
            Flash.setMessage('An error occurred. Please try again.', 'error');
        }
    }

    async handleMessageUpdate(messageId, newContent, container) {
        if (this.isStreaming) {
            const sendButton = container?.querySelector('.edit-form .edit-send');
            if (sendButton) {
                sendButton.disabled = true;
                sendButton.textContent = 'Send';
            }
            return;
        }

        await this.storage.updateMessage(messageId, newContent);

        const contentElement = container.querySelector('.content');
        contentElement.style.whiteSpace = 'pre-wrap';
        contentElement.innerText = newContent;

        this.view.hideEditForm(container);
        this.removeMessagesAfter(container);
        await this.view.scrollMessageToTop(container);
        this.updateMessagesArray(messageId, newContent);
        await this.renderAssistantMessage();
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
        const targetId = String(editedMessageId);
        const index = this.messages.findIndex((m) => String(m.message_id ?? m.id ?? '') === targetId);
        if (index === -1) return;
        if (this.messages[index]) this.messages[index].content = newContent;
        this.messages.splice(index + 1);
    }

    async renderAssistantMessage() {
        this.view.disableNew();
        this.view.enableAbort();
        this.isStreaming = true;
        this.setEditFormSubmissionEnabled(false);
        this.updateSendButtonState();

        const streamedTurnEvents = [];
        const turnId = this.createTurnId();
        let turnUi = null;
        const hasVisibleText = (rawText) => String(rawText || '').trim().length > 0;
        const discardFinalizedSegment = (finalized) => {
            finalized.container.remove();
        };
        const appendAssistantTurnEvent = (event) => {
            streamedTurnEvents.push(event);
        };
        const persistFinalizedAnswer = (displayText) => {
            appendAssistantTurnEvent({
                event_type: 'assistant_segment',
                reasoning_text: '',
                content_text: displayText,
            });
        };
        const persistFinalizedThinking = (displayText) => {
            appendAssistantTurnEvent({
                event_type: 'assistant_segment',
                reasoning_text: displayText,
                content_text: '',
            });
        };
        const appendToolTurnEvent = (toolCall) => {
            appendAssistantTurnEvent({
                event_type: 'tool_call',
                tool_call_id: String(toolCall.tool_call_id || ''),
                tool_name: String(toolCall.tool_name || ''),
                arguments_json: String(toolCall.arguments_json || '{}'),
                result_text: String(toolCall.content || ''),
                error_text: String(toolCall.error_text || ''),
            });
        };
        const buildAssistantMessagesFromTurnEvents = (events) => (
            Array.isArray(events)
                ? events
                    .filter((event) => event?.event_type === 'assistant_segment')
                    .map((event) => String(event?.content_text || ''))
                    .filter((contentText) => hasVisibleText(contentText))
                    .map((content) => ({ role: 'assistant', content }))
                : []
        );

        const ensureAssistantContainer = async (kind = 'Thinking', options = {}) => {
            if (!turnUi) {
                turnUi = this.view.createAssistantTurn();
            }
            let segment = turnUi.ensureAssistantSegment(kind, options);
            if (!segment) {
                await finalizeAssistantContainer();
                segment = turnUi.ensureAssistantSegment(kind, options);
            }
            return segment;
        };
        const classifyFinalizedSegment = (finalized) => {
            const kind = String(finalized?.kind || '').toLowerCase();
            const text = String(finalized?.text || '');
            const isVisible = Boolean(finalized?.isVisible);
            if (!isVisible || !hasVisibleText(text)) {
                return { action: 'discard', text };
            }
            if (kind === 'answer') {
                return { action: 'answer', text };
            }
            if (kind === 'thinking') {
                return { action: 'thinking', text };
            }
            return { action: 'discard', text };
        };

        const finalizeAssistantContainer = async () => {
            if (!turnUi) return;
            const finalized = await turnUi.finalizeAssistantSegment();
            if (!finalized) return;
            const classified = classifyFinalizedSegment(finalized);

            if (classified.action === 'discard') {
                discardFinalizedSegment(finalized);
                return;
            }

            if (classified.action === 'answer') {
                persistFinalizedAnswer(classified.text);
                return;
            }

            if (classified.action === 'thinking') {
                persistFinalizedThinking(classified.text);
                return;
            }

            discardFinalizedSegment(finalized);
        };

        try {
            for await (const chunk of this.chat.stream({
                model: this.view.getSelectedModel(),
                dialog_id: this.dialogId || '',
                messages: this.messages,
            }, this.abortController.signal)) {
                if (chunk.toolStatus) {
                    const currentSegment = turnUi?.getActiveAssistantSegment?.();
                    if (currentSegment && currentSegment.segmentKind !== 'tool') {
                        await finalizeAssistantContainer();
                    }
                    const activeUi = await ensureAssistantContainer('Tool', { showLoader: true, transient: true, hideStep: true });
                    activeUi.setLoading(true);
                    const toolName = String(chunk.toolStatus.tool_name || 'tool');
                    activeUi.setStatus(`Calling tool: ${toolName}...`);
                    continue;
                }
                if (chunk.toolCall) {
                    await finalizeAssistantContainer();
                    if (!turnUi) {
                        turnUi = this.view.createAssistantTurn();
                    }
                    turnUi.appendToolCall(chunk.toolCall);
                    appendToolTurnEvent(chunk.toolCall);
                    continue;
                }

                if (chunk.reasoningOpenClose || chunk.reasoning) {
                    const activeUi = await ensureAssistantContainer('Thinking');
                    activeUi.setLoading(true);
                    activeUi.clearStatus();
                    if (chunk.reasoning) {
                        void activeUi.appendText(chunk.reasoning);
                    }
                }

                if (chunk.content) {
                    const activeUi = await ensureAssistantContainer('Answer');
                    activeUi.setLoading(false);
                    activeUi.clearStatus();
                    void activeUi.appendText(chunk.content, Boolean(chunk.done));
                }
            }
        } catch (error) {
            if (turnUi) {
                const activeUi = turnUi.getActiveAssistantSegment();
                if (activeUi) {
                    activeUi.setLoading(false);
                }
            }
            if (error.name === 'AbortError') {
                Flash.setMessage('Request was aborted', 'notice');
            } else {
                const message = (typeof error?.message === 'string' && error.message.trim())
                    ? error.message.trim()
                    : 'An error occurred while processing the stream.';
                Flash.setMessage(message, 'error');
            }
        } finally {
            this.isStreaming = false;
            this.setEditFormSubmissionEnabled(true);
            this.view.disableAbort();
            this.view.enableNew();
            this.updateSendButtonState();

            await finalizeAssistantContainer();

            if (this.dialogId && streamedTurnEvents.length > 0) {
                await this.storage.createAssistantTurnEvents(this.dialogId, {
                    turn_id: turnId,
                    events: streamedTurnEvents,
                });
            }

            for (const message of buildAssistantMessagesFromTurnEvents(streamedTurnEvents)) {
                this.messages.push(message);
            }
            if (turnUi) {
                const liveTurnContainer = turnUi.container;
                if (streamedTurnEvents.length > 0) {
                    const segmentOpenStates = Array.from(
                        liveTurnContainer.querySelectorAll('.assistant-segment-header.assistant-segment-toggle'),
                    ).map((toggle) => String(toggle.getAttribute('aria-expanded') || '').toLowerCase() === 'true');
                    await this.view.renderStaticAssistantTurn(streamedTurnEvents, liveTurnContainer, { segmentOpenStates });
                    liveTurnContainer.remove();
                } else {
                    turnUi.removeIfEmpty();
                }
                turnUi = null;
            }
            this.abortController = new AbortController();
        }
    }

    async loadDialog(savedMessages) {
        this.messages = [];
        for (const msg of savedMessages) {
            if (msg.role === 'user' || msg.role === 'system') {
                this.messages.push(msg);
                continue;
            }
            if (msg.role === 'assistant_turn' && Array.isArray(msg.events)) {
                for (const event of msg.events) {
                    if (event?.event_type !== 'assistant_segment') continue;
                    const contentText = String(event?.content_text || '');
                    if (!contentText.trim()) continue;
                    this.messages.push({ role: 'assistant', content: contentText, images: [] });
                }
            }
        }
        responsesElem.innerHTML = '';

        for (const msg of savedMessages) {
            if (msg.role === 'user' || msg.role === 'system') {
                const displayRole = msg.role === 'system' ? 'System' : 'User';
                this.view.renderStaticUserMessage(
                    msg.content,
                    msg.message_id,
                    async (id, newContent, container) => {
                        await this.handleMessageUpdate(id, newContent, container);
                    },
                    msg.images || [],
                    msg.attachments || [],
                    displayRole,
                );
                continue;
            }

            if (msg.role === 'assistant_turn') {
                await this.view.renderStaticAssistantTurn(msg.events || []);
                continue;
            }

            if (msg.role === 'assistant') {
                await this.view.renderStaticAssistantMessage(msg.content, msg.message_id);
                continue;
            }

            if (msg.role === 'tool') {
                this.view.renderStaticToolMessage(msg);
            }
        }
    }

    async initializeDialog(dialogID) {
        try {
            const allMessages = await this.storage.getMessages(dialogID);
            await this.loadDialog(allMessages);
        } catch (error) {
            console.error('Error in initializeDialog:', error);
            Flash.setMessage('An error occurred. Please try again.', 'error');
        }
    }

    async initializeFromPrompt(promptID) {
        try {
            const promptData = await Requests.asyncGetJson(`/prompt/${promptID}/json`);
            const promptText = promptData.prompt.prompt;
            const promptRole = this.getInitialPromptRole();

            const promptContainer = this.view.renderStaticUserMessage(
                promptText,
                null,
                async (id, newContent, container) => {
                    await this.handleMessageUpdate(id, newContent, container);
                },
                [],
                [],
                promptRole === 'system' ? 'System' : 'User',
            );
            await this.view.scrollMessageToTop(promptContainer);

            this.messages = [{ role: promptRole, content: promptText, images: [], attachments: [] }];

            const url = new URL(window.location.href);
            url.searchParams.delete('id');
            window.history.replaceState({}, document.title, `${url.pathname}${url.search}`);
        } catch (error) {
            console.error('Error in initializeFromPrompt:', error);
            Flash.setMessage('An error occurred while initializing from prompt.', 'error');
        }
    }
}

export { ConversationController };
