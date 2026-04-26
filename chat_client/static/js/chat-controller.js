import { Flash } from '/static/js/flash.js';
import { logError } from '/static/js/error-log.js';
import { Requests } from '/static/js/requests.js';
import { openImagePreviewModal, closeImagePreviewModal } from '/static/js/image-preview-modal.js';

const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024;
const MAX_CONVERSATION_UPLOADS = 10;

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
        this.bottomSentinel = null;
        this.bottomSentinelVisible = false;
        this.bottomSentinelMeasured = false;
        this.bottomSentinelObserverMargin = null;
        this.bottomSentinelObserver = null;

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
        const modelCapabilities = this.config?.model_capabilities;
        if (modelCapabilities && typeof modelCapabilities === 'object' && modelCapabilities[selectedModel]) {
            return modelCapabilities[selectedModel];
        }
        const visionModels = Array.isArray(this.config.vision_models) ? this.config.vision_models : [];
        return {
            supports_images: visionModels.includes(selectedModel),
            supports_attachments: true,
            supports_tools: false,
            supports_reasoning: false,
        };
    }

    selectedModelSupportsImages() {
        return Boolean(this.getSelectedModelCapabilities()?.supports_images);
    }

    selectedModelSupportsAttachments() {
        return Boolean(this.getSelectedModelCapabilities()?.supports_attachments);
    }

    selectedModelSupportsReasoningEffort() {
        return Boolean(this.getSelectedModelCapabilities()?.supports_reasoning);
    }

    getSelectedReasoningEffort() {
        if (!this.selectedModelSupportsReasoningEffort()) {
            return '';
        }
        const selectedValue = String(this.reasoningSelection.getSelectedValue() || '').trim().toLowerCase();
        if (selectedValue === 'none') {
            return '';
        }
        if (['low', 'medium', 'high'].includes(selectedValue)) {
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

    getBottomSentinel() {
        const { responsesElem } = this.elements;
        return responsesElem.querySelector('.responses-anchor-spacer');
    }

    ensureBottomSentinelObserver() {
        const { scrollToBottom, promptElem } = this.elements;
        if (!scrollToBottom || typeof IntersectionObserver === 'undefined') {
            return;
        }

        const promptHeight = Math.ceil(promptElem?.getBoundingClientRect().height || 0);
        const observerMargin = `0px 0px -${promptHeight}px 0px`;

        if (this.bottomSentinelObserver && this.bottomSentinelObserverMargin !== observerMargin) {
            if (this.bottomSentinel) {
                this.bottomSentinelObserver.unobserve(this.bottomSentinel);
            }
            this.bottomSentinelObserver.disconnect();
            this.bottomSentinelObserver = null;
            this.bottomSentinelMeasured = false;
        }

        if (!this.bottomSentinelObserver) {
            this.bottomSentinelObserver = new IntersectionObserver((entries) => {
                const entry = entries[entries.length - 1];
                if (!entry || entry.target !== this.bottomSentinel) return;
                this.bottomSentinelMeasured = true;
                this.bottomSentinelVisible = entry.isIntersecting;
                this.checkScroll();
            }, {
                rootMargin: observerMargin,
            });
            this.bottomSentinelObserverMargin = observerMargin;
        }

        const sentinel = this.getBottomSentinel();
        if (!sentinel || sentinel === this.bottomSentinel) {
            return;
        }

        if (this.bottomSentinel) {
            this.bottomSentinelObserver.unobserve(this.bottomSentinel);
        }

        this.bottomSentinel = sentinel;
        this.bottomSentinelMeasured = false;
        this.bottomSentinelObserver.observe(sentinel);
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
                const uploaded = await this.storage.uploadAttachment(file, {
                    dialogId: this.dialogId || '',
                    pendingAttachmentIds: this.pendingAttachments
                        .map((attachment) => attachment?.attachment_id)
                        .filter((attachmentId) => attachmentId !== null && attachmentId !== undefined),
                    pendingImageCount: this.pendingImages.length,
                });
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

        imageInputElem.value = '';
        this.renderPendingUploads();
        this.updateSendButtonState();
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
                const uploaded = await this.storage.uploadAttachment(file, {
                    dialogId: this.dialogId || '',
                    pendingAttachmentIds: this.pendingAttachments
                        .map((attachment) => attachment?.attachment_id)
                        .filter((attachmentId) => attachmentId !== null && attachmentId !== undefined),
                    pendingImageCount: this.pendingImages.length,
                });
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

        new MutationObserver(() => {
            this.ensureBottomSentinelObserver();
            this.checkScroll();
            if (this.isStreaming) this.setEditFormSubmissionEnabled(false);
        }).observe(responsesElem, { childList: true, subtree: true });
    }

    wireUI() {
        this.ensureBottomSentinelObserver();
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
        const { responsesElem } = this.elements;
        const isEditingMessage = Boolean(responsesElem.querySelector('.edit-form'));

        const doc = document.documentElement;
        const hasScrollbar = doc.scrollHeight > window.innerHeight;
        if (!hasScrollbar || isEditingMessage) {
            this.setScrollToBottomVisible(false);
            return;
        }

        const spacerHeight = this.bottomSentinel
            ? Math.ceil(this.bottomSentinel.getBoundingClientRect().height || 0)
            : 0;
        const contentBottom = Math.max(0, doc.scrollHeight - spacerHeight);
        const distanceFromContentBottom = Math.max(0, contentBottom - (window.innerHeight + window.scrollY));
        const hideThreshold = 12;
        if (distanceFromContentBottom <= hideThreshold) {
            this.setScrollToBottomVisible(false);
            return;
        }

        if (this.bottomSentinel && this.bottomSentinelObserver) {
            if (!this.bottomSentinelMeasured) {
                this.setScrollToBottomVisible(false);
                return;
            }
            this.setScrollToBottomVisible(!this.bottomSentinelVisible);
            return;
        }

        const distanceFromBottom = Math.max(0, doc.scrollHeight - (window.innerHeight + window.scrollY));
        if (distanceFromBottom <= hideThreshold) {
            this.setScrollToBottomVisible(false);
            return;
        }

        this.setScrollToBottomVisible(true);
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
        const supportsSystemMessages = Boolean(this.getSelectedModelCapabilities()?.supports_system_messages);
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

    async renderAssistantMessage(options = {}) {
        const shouldGenerateTitle = Boolean(options?.shouldGenerateTitle);
        const modelName = String(options?.model || this.modelSelection.getSelectedModel() || '');
        const reasoningEffort = String(options?.reasoningEffort || this.getSelectedReasoningEffort() || '');
        this.view.disableNew();
        this.view.enableAbort();
        this.isStreaming = true;
        this.setEditFormSubmissionEnabled(false);
        this.updateSendButtonState();

        const streamedTurnEvents = [];
        const fallbackTurnId = this.createTurnId();
        let turnId = '';
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
        const ensureLoadingAnswerContainer = async () => {
            const segment = await ensureAssistantContainer('Answer', {
                showLoader: true,
                transient: true,
                previewStep: true,
                displayKind: 'Waiting for model',
            });
            segment.setLoading(true);
            segment.clearStatus();
            return segment;
        };
        const activateToolStatusSegment = async (toolName = 'tool') => {
            const activeUi = await ensureAssistantContainer('Tool', {
                showLoader: true,
                transient: true,
                previewStep: true,
            });
            activeUi.setLoading(true);
            activeUi.setStatus(`Calling tool: ${String(toolName || 'tool')}...`);
            return activeUi;
        };
        const activateThinkingSegment = async () => {
            const activeUi = await ensureAssistantContainer('Thinking');
            activeUi.setLoading(true);
            activeUi.clearStatus();
            return activeUi;
        };
        const activateAnswerSegment = async () => {
            const activeUi = await ensureAssistantContainer('Answer');
            activeUi.promote?.({ kind: 'Answer', showStep: true });
            activeUi.setLoading(true);
            activeUi.clearStatus();
            return activeUi;
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
            await ensureLoadingAnswerContainer();
            for await (const chunk of this.chat.stream({
                model: modelName,
                reasoning_effort: reasoningEffort,
                dialog_id: this.dialogId || '',
                messages: this.messages,
            }, this.abortController.signal)) {
                if (chunk.turnId) {
                    turnId = String(chunk.turnId || '').trim();
                    continue;
                }
                if (chunk.toolStatus) {
                    const currentSegment = turnUi?.getActiveAssistantSegment?.();
                    if (currentSegment && currentSegment.segmentKind !== 'tool') {
                        await finalizeAssistantContainer();
                    }
                    await activateToolStatusSegment(chunk.toolStatus.tool_name);
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
                    const activeUi = await activateThinkingSegment();
                    if (chunk.reasoning) {
                        void activeUi.appendText(chunk.reasoning);
                    }
                }

                if (chunk.content) {
                    const activeUi = await activateAnswerSegment();
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

            await finalizeAssistantContainer();

            if (this.dialogId && streamedTurnEvents.length > 0) {
                await this.storage.createAssistantTurnEvents(this.dialogId, {
                    turn_id: turnId || fallbackTurnId,
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
