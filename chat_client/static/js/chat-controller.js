import { Flash } from '/static/js/flash.js';
import { logError } from '/static/js/error-log.js';
import { Requests } from '/static/js/requests.js';
import { openImagePreviewModal, closeImagePreviewModal } from '/static/js/image-preview-modal.js';
import { createAssistantStreamSession } from '/static/js/chat-assistant-stream-session.js';
import { buildAssistantMessagesFromTurnEvents } from '/static/js/chat-turn-events.js';

const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024;
const MAX_CONVERSATION_UPLOADS = 10;
const DEFAULT_MODEL_CAPABILITIES = {
    supports_images: false,
    supports_attachments: false,
    supports_tools: false,
    supports_reasoning: false,
    supports_thinking: false,
    supports_thinking_control: false,
    supports_system_messages: true,
    context_length: null,
};

class ConversationController {
    constructor({ view, storage, chat, config, elements, modelSelection, reasoningSelection }) {
        this.view = view;
        this.storage = storage;
        this.chat = chat;
        this.config = config;
        this.elements = elements;
        this.modelSelection = modelSelection;
        this.reasoningSelection = reasoningSelection;
        this.isInitializing = true;
        this.isSubmitting = false;
        this.isStreaming = false;
        this.messages = [];
        this.dialogId = null;
        this.abortController = new AbortController();
        this.pendingImages = [];
        this.pendingAttachments = [];
        this.activeAssistantRenderPromise = Promise.resolve();

        this.wireUI();
        this.updateAttachmentUI();
        this.updateSendButtonState();
        this.renderPendingUploads();
    }

    setEditFormSubmissionEnabled(enabled) {
        const { responsesElem } = this.elements;
        const editSendButtons = responsesElem.querySelectorAll('.edit-form .edit-send');
        editSendButtons.forEach((button) => {
            button.disabled = !enabled;
        });
    }

    getSelectedModelCapabilities() {
        const selectedModel = this.modelSelection.getSelectedModel();
        const modelCapabilities = this.config.model_capabilities;
        if (modelCapabilities && typeof modelCapabilities === 'object' && modelCapabilities[selectedModel]) {
            return {
                ...DEFAULT_MODEL_CAPABILITIES,
                ...modelCapabilities[selectedModel],
            };
        }
        const visionModels = Array.isArray(this.config.vision_models) ? this.config.vision_models : [];
        return {
            ...DEFAULT_MODEL_CAPABILITIES,
            supports_images: visionModels.includes(selectedModel),
        };
    }

    selectedModelSupportsImages() {
        return Boolean(this.getSelectedModelCapabilities().supports_images);
    }

    selectedModelSupportsAttachments() {
        return Boolean(this.getSelectedModelCapabilities().supports_attachments);
    }

    selectedModelSupportsReasoningEffort() {
        const capabilities = this.getSelectedModelCapabilities();
        return Boolean(
            capabilities.supports_thinking_control
            || capabilities.supports_reasoning
            || capabilities.supports_thinking,
        );
    }

    getSelectedReasoningEffort() {
        if (!this.selectedModelSupportsReasoningEffort()) {
            return '';
        }
        const selectedValue = String(this.reasoningSelection.getSelectedValue() || '').trim().toLowerCase();
        if (['none', 'low', 'medium', 'high'].includes(selectedValue)) {
            return selectedValue;
        }
        return '';
    }

    updateAttachmentUI() {
        const {
            attachImageButtonElem,
            imageInputElem,
            attachFileButtonElem,
            attachmentInputElem,
            reasoningPickerElem,
        } = this.elements;
        const supportsImages = this.selectedModelSupportsImages();
        const supportsAttachments = this.selectedModelSupportsAttachments();
        const supportsReasoningEffort = this.selectedModelSupportsReasoningEffort();
        attachImageButtonElem.classList.toggle('hidden', !supportsImages);
        attachImageButtonElem.disabled = !supportsImages;
        imageInputElem.disabled = !supportsImages;
        attachFileButtonElem.classList.toggle('hidden', !supportsAttachments);
        attachFileButtonElem.disabled = !supportsAttachments;
        attachmentInputElem.disabled = !supportsAttachments;
        reasoningPickerElem.classList.toggle('hidden', !supportsReasoningEffort);

        if (!supportsImages && this.pendingImages.length > 0) {
            this.clearPendingImages();
        }
        if (!supportsAttachments && this.pendingAttachments.length > 0) {
            this.clearPendingAttachments();
        }
    }

    updateSendButtonState() {
        const { messageElem } = this.elements;
        const hasText = messageElem.value.trim().length > 0;
        const hasImages = this.selectedModelSupportsImages() && this.pendingImages.length > 0;
        const hasAttachments = this.selectedModelSupportsAttachments() && this.pendingAttachments.length > 0;
        const canSend = !this.isInitializing && !this.isSubmitting && !this.isStreaming && (hasText || hasImages || hasAttachments);

        if (canSend) {
            this.view.enableSend();
        } else {
            this.view.disableSend();
        }
    }

    renderPendingUploads() {
        this.view.renderPendingUploads(this.pendingImages, this.pendingAttachments, {
            onOpenImagePreview: (dataUrl, name) => {
                this.openImagePreviewModal(dataUrl, name);
            },
            onOpenAttachmentPreview: (attachmentId) => {
                window.open(`/api/chat/attachments/${attachmentId}/preview`, '_blank', 'noopener');
            },
            onRemovePendingImage: (imageId) => {
                this.pendingImages = this.pendingImages.filter(
                    (pending) => String(pending.attachment_id || pending.id) !== String(imageId),
                );
                this.renderPendingUploads();
                this.updateSendButtonState();
            },
            onRemovePendingAttachment: (attachmentId) => {
                this.pendingAttachments = this.pendingAttachments.filter(
                    (pending) => String(pending.attachment_id) !== String(attachmentId),
                );
                this.renderPendingUploads();
                this.updateSendButtonState();
            },
        });
    }

    openImagePreviewModal(dataUrl, name) {
        const { imagePreviewModalElem, imagePreviewModalImageElem } = this.elements;
        openImagePreviewModal(imagePreviewModalElem, imagePreviewModalImageElem, dataUrl, name);
    }

    getLastResponseElement() {
        const { responsesElem } = this.elements;
        const children = Array.from(responsesElem.children);
        for (let index = children.length - 1; index >= 0; index -= 1) {
            const child = children[index];
            if (!child.classList.contains('responses-anchor-spacer')) {
                return child;
            }
        }
        return null;
    }

    closeImagePreviewModal() {
        const { imagePreviewModalElem, imagePreviewModalImageElem } = this.elements;
        closeImagePreviewModal(imagePreviewModalElem, imagePreviewModalImageElem);
    }

    clearPendingImages() {
        const { imageInputElem } = this.elements;
        this.pendingImages = [];
        imageInputElem.value = '';
        this.closeImagePreviewModal();
        this.renderPendingUploads();
        this.updateSendButtonState();
    }

    clearPendingAttachments() {
        const { attachmentInputElem } = this.elements;
        this.pendingAttachments = [];
        attachmentInputElem.value = '';
        this.renderPendingUploads();
        this.updateSendButtonState();
    }

    setScrollToBottomVisible(isVisible) {
        const { scrollToBottom } = this.elements;
        if (!scrollToBottom) return;
        scrollToBottom.classList.toggle('is-visible', Boolean(isVisible));
    }

    getConversationUploadCount() {
        let persistedCount = 0;
        for (const message of this.messages) {
            if (!message || (message.role !== 'user' && message.role !== 'system')) continue;
            persistedCount += Array.isArray(message.images) ? message.images.length : 0;
            persistedCount += Array.isArray(message.attachments) ? message.attachments.length : 0;
        }
        return persistedCount + this.pendingImages.length + this.pendingAttachments.length;
    }

    getUploadContext() {
        return {
            dialogId: this.dialogId || '',
            pendingAttachmentIds: this.pendingAttachments
                .map((attachment) => attachment?.attachment_id)
                .filter((attachmentId) => attachmentId !== null && attachmentId !== undefined),
            pendingImageCount: this.pendingImages.length,
        };
    }

    finishUploadSelection(inputElem) {
        inputElem.value = '';
        this.renderPendingUploads();
        this.updateSendButtonState();
    }

    async handleImageSelection(files) {
        const { imageInputElem } = this.elements;
        if (!this.selectedModelSupportsImages()) {
            this.clearPendingImages();
            imageInputElem.value = '';
            Flash.setMessage('The selected model does not support image inputs.', 'notice');
            return;
        }

        const selectedFiles = Array.from(files || []);
        if (!selectedFiles.length) return;

        for (const file of selectedFiles) {
            if (this.getConversationUploadCount() >= MAX_CONVERSATION_UPLOADS) {
                Flash.setMessage(`You can attach at most ${MAX_CONVERSATION_UPLOADS} images/files in a single conversation.`, 'notice');
                break;
            }
            if (!file.type.startsWith('image/')) {
                Flash.setMessage(`Skipped ${file.name}: file is not an image`, 'notice');
                continue;
            }
            if (file.size > MAX_IMAGE_SIZE_BYTES) {
                Flash.setMessage(`Skipped ${file.name}: file is larger than 10MB`, 'notice');
                continue;
            }
            try {
                const uploaded = await this.storage.uploadAttachment(file, this.getUploadContext());
                this.pendingImages.push({
                    attachment_id: uploaded.attachment_id,
                    name: uploaded.name || file.name,
                    content_type: uploaded.content_type || file.type,
                    size_bytes: uploaded.size_bytes || file.size,
                    previewUrl: `/api/chat/attachments/${uploaded.attachment_id}/preview`,
                });
            } catch (error) {
                console.error('Error uploading image:', error);
                Flash.setMessage(
                    Requests.getErrorMessage(error, `Skipped ${file.name}: could not upload image`),
                    'notice',
                );
            }
        }

        this.finishUploadSelection(imageInputElem);
    }

    async handleAttachmentSelection(files) {
        const { attachmentInputElem } = this.elements;
        if (!this.selectedModelSupportsAttachments()) {
            this.clearPendingAttachments();
            attachmentInputElem.value = '';
            Flash.setMessage('The selected model does not support file attachments.', 'notice');
            return;
        }

        const selectedFiles = Array.from(files || []);
        if (!selectedFiles.length) return;

        for (const file of selectedFiles) {
            try {
                const uploaded = await this.storage.uploadAttachment(file, this.getUploadContext());
                this.pendingAttachments.push(uploaded);
            } catch (error) {
                console.error('Error uploading attachment:', error);
                Flash.setMessage(
                    Requests.getErrorMessage(error, `Skipped ${file.name}: could not upload file`),
                    'notice',
                );
            }
        }

        this.finishUploadSelection(attachmentInputElem);
    }

    bindFormEvents() {
        const { messageFormElem, sendButtonElem, abortButtonElem } = this.elements;

        messageFormElem.addEventListener('submit', (event) => {
            event.preventDefault();
        });

        sendButtonElem.addEventListener('click', async () => {
            await this.sendUserMessage();
        });

        abortButtonElem.addEventListener('click', () => {
            this.abortController.abort();
            this.abortController = new AbortController();
        });
    }

    bindMessageEvents() {
        const { responsesElem, messageElem } = this.elements;

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

        messageElem.addEventListener('keydown', async (event) => {
            if (event.key !== 'Enter') return;
            if (event.ctrlKey) {
                event.preventDefault();
                const start = messageElem.selectionStart;
                const end = messageElem.selectionEnd;
                messageElem.value = messageElem.value.substring(0, start) + '\n' + messageElem.value.substring(end);
                messageElem.selectionStart = messageElem.selectionEnd = start + 1;
                this.view.resizeInput();
                this.updateSendButtonState();
                return;
            }
            event.preventDefault();
            await this.sendUserMessage();
        });
    }

    bindAttachmentEvents() {
        const {
            imageInputElem,
            attachImageButtonElem,
            attachmentInputElem,
            attachFileButtonElem,
        } = this.elements;

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

        imageInputElem.addEventListener('change', async (event) => {
            await this.handleImageSelection(event.target.files);
        });

        attachmentInputElem.addEventListener('change', async (event) => {
            await this.handleAttachmentSelection(event.target.files);
        });
    }

    bindModalEvents() {
        const { imagePreviewModalElem, imagePreviewModalCloseElem } = this.elements;

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
    }

    bindScrollEvents() {
        const { responsesElem, scrollToBottom } = this.elements;

        scrollToBottom.addEventListener('click', () => {
            window.scrollTo({
                top: document.documentElement.scrollHeight,
                behavior: 'smooth',
            });
        });

        window.addEventListener('scroll', () => {
            this.checkScroll();
        }, { passive: true });

        window.addEventListener('resize', () => {
            this.checkScroll();
        });

        new MutationObserver(() => {
            this.checkScroll();
            if (this.isStreaming) this.setEditFormSubmissionEnabled(false);
        }).observe(responsesElem, { childList: true, subtree: true });
    }

    wireUI() {
        this.modelSelection.subscribe(() => {
            this.updateAttachmentUI();
            this.updateSendButtonState();
        });
        this.reasoningSelection.subscribe(() => {
            this.updateSendButtonState();
        });
        this.bindFormEvents();
        this.bindMessageEvents();
        this.bindAttachmentEvents();
        this.bindModalEvents();
        this.bindScrollEvents();
    }

    checkScroll() {
        const { responsesElem, promptElem } = this.elements;
        const isEditingMessage = Boolean(responsesElem.querySelector('.edit-form'));

        const doc = document.documentElement;
        const hasScrollbar = doc.scrollHeight > window.innerHeight;
        if (!hasScrollbar || isEditingMessage) {
            this.setScrollToBottomVisible(false);
            return;
        }

        const lastResponseElem = this.getLastResponseElement();
        if (!lastResponseElem) {
            this.setScrollToBottomVisible(false);
            return;
        }

        const promptHeight = Math.ceil(promptElem?.getBoundingClientRect().height || 0);
        const visibleBottom = window.innerHeight - promptHeight;
        const hideThreshold = 12;
        const lastResponseBottom = lastResponseElem.getBoundingClientRect().bottom;
        this.setScrollToBottomVisible(lastResponseBottom > (visibleBottom + hideThreshold));
    }

    validateUserMessage(userMessage) {
        const hasImages = this.selectedModelSupportsImages() && this.pendingImages.length > 0;
        const hasAttachments = this.selectedModelSupportsAttachments() && this.pendingAttachments.length > 0;
        return !!(
            this.isInitializing === false
            && this.isSubmitting === false
            && this.isStreaming === false
            && (userMessage || hasImages || hasAttachments)
        );
    }

    getInitialPromptRole() {
        const supportsSystemMessages = Boolean(this.getSelectedModelCapabilities().supports_system_messages);
        return supportsSystemMessages ? 'system' : 'user';
    }

    createTurnId() {
        if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
            return globalThis.crypto.randomUUID();
        }
        return `turn-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    setInitializing(isInitializing) {
        this.isInitializing = Boolean(isInitializing);
        this.updateSendButtonState();
    }

    async sendUserMessage() {
        const { messageElem } = this.elements;
        if (this.isSubmitting || this.isStreaming) return;
        try {
            const userMessage = messageElem.value.trim();
            const images = this.selectedModelSupportsImages()
                ? this.pendingImages.map((img) => ({
                    attachment_id: img.attachment_id,
                    name: img.name,
                    content_type: img.content_type,
                    size_bytes: img.size_bytes,
                }))
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
            this.isSubmitting = true;
            this.updateSendButtonState();
            const message = { role: 'user', content: userMessage, images: images, attachments };
            let createdNewDialog = false;

            if (!this.dialogId) {
                this.dialogId = await this.storage.createDialog('', userMessage);
                createdNewDialog = true;

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
                content: userMessage,
                model: this.modelSelection.getSelectedModel(),
                images,
                attachments,
            });

            this.messages.push({ ...message, message_id: userMessageId });

            this.view.clearInput();
            this.clearPendingImages();
            this.clearPendingAttachments();

            const userContainer = this.view.renderStaticUserMessage(
                userMessage,
                userMessageId,
                async (id, newContent, container) => {
                    await this.handleMessageUpdate(id, newContent, container);
                },
                images,
                attachments,
            );

            await this.view.scrollMessageToTop(userContainer);

            // Release submit state before the assistant stream starts so the
            // composer can re-enable as soon as streaming finishes, even if
            // post-stream persistence/render cleanup is still running.
            this.isSubmitting = false;
            this.updateSendButtonState();

            await this.renderAssistantMessage({
                shouldGenerateTitle: createdNewDialog && Boolean(userMessage),
                model: this.modelSelection.getSelectedModel(),
                reasoningEffort: this.getSelectedReasoningEffort(),
            });
        } catch (error) {
            await logError(error, 'Error in sendUserMessage');
            console.error('Error in sendUserMessage:', error);
            if (typeof error?.redirect === 'string' && error.redirect.trim()) {
                window.location.href = error.redirect;
                return;
            }
            Flash.setMessage(
                Requests.getErrorMessage(error, 'An error occurred. Please try again.'),
                'error',
            );
        } finally {
            this.isSubmitting = false;
            this.updateSendButtonState();
        }
    }

    async handleMessageUpdate(messageId, newContent, container) {
        if (this.isStreaming) {
            const sendButton = container?.querySelector('.edit-form .edit-send');
            if (sendButton) {
                sendButton.disabled = true;
                sendButton.textContent = 'Waiting...';
            }
            await this.activeAssistantRenderPromise.catch(() => {});
            if (sendButton) {
                sendButton.textContent = 'Sending...';
            }
        }

        await this.storage.updateMessage(messageId, newContent);

        const contentElement = container.querySelector('.content');
        contentElement.style.whiteSpace = 'pre-wrap';
        contentElement.innerText = newContent;
        this.view.updateCopyMessage(container, newContent);

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

    async renderAssistantMessage(options = {}) {
        const renderPromise = this._renderAssistantMessage(options);
        this.activeAssistantRenderPromise = renderPromise.catch(() => {});
        return renderPromise;
    }

    async _renderAssistantMessage(options = {}) {
        const shouldGenerateTitle = Boolean(options.shouldGenerateTitle);
        const modelName = String(options.model || this.modelSelection.getSelectedModel() || '');
        const reasoningEffort = String(options.reasoningEffort || this.getSelectedReasoningEffort() || '');
        this.view.disableNew();
        this.view.enableAbort();
        this.isStreaming = true;
        this.setEditFormSubmissionEnabled(false);
        this.updateSendButtonState();

        const fallbackTurnId = this.createTurnId();
        const streamSession = createAssistantStreamSession({ view: this.view });
        let streamedTurnEvents = [];
        let turnId = '';

        try {
            await streamSession.start();
            for await (const chunk of this.chat.stream({
                model: modelName,
                reasoning_effort: reasoningEffort,
                dialog_id: this.dialogId || '',
                messages: this.messages,
            }, this.abortController.signal)) {
                await streamSession.processChunk(chunk);
            }
        } catch (error) {
            streamSession.clearActiveSegmentLoading();
            if (error.name === 'AbortError') {
                Flash.setMessage('Request was aborted', 'notice');
            } else if (error?.status === 401 && typeof error?.redirect === 'string' && error.redirect.trim()) {
                window.location.href = error.redirect;
                return;
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

            const finalizedTurn = await streamSession.finalize();
            streamedTurnEvents = finalizedTurn.events;
            turnId = finalizedTurn.turnId;

            if (this.dialogId && streamedTurnEvents.length > 0) {
                await this.storage.createAssistantTurnEvents(this.dialogId, {
                    turn_id: turnId || fallbackTurnId,
                    events: streamedTurnEvents,
                });
            }

            for (const message of buildAssistantMessagesFromTurnEvents(streamedTurnEvents)) {
                this.messages.push(message);
            }
            if (shouldGenerateTitle && this.dialogId) {
                void this.storage.generateDialogTitle(this.dialogId).catch((titleError) => {
                    console.warn('Failed to generate dialog title:', titleError);
                });
            }
            this.abortController = new AbortController();
        }
    }

    async loadDialog(savedMessages) {
        const { responsesElem } = this.elements;
        this.messages = [];
        for (const msg of savedMessages) {
            if (msg.role === 'user' || msg.role === 'system') {
                this.messages.push(msg);
                continue;
            }
            if (msg.role === 'assistant_turn' && Array.isArray(msg.events)) {
                this.messages.push(...buildAssistantMessagesFromTurnEvents(msg.events).map((message) => ({
                    ...message,
                    images: [],
                })));
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
                    msg.role !== 'system',
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
            const promptData = await Requests.asyncGetJson(`/api/prompts/${promptID}`);
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
