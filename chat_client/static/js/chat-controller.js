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
    imagePreviewElem,
    attachImageButtonElem,
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

        this.wireUI();
        this.updateImageAttachmentUI();
        this.updateSendButtonState();
    }

    setEditFormSubmissionEnabled(enabled) {
        const editSendButtons = responsesElem.querySelectorAll('.edit-form .edit-send');
        editSendButtons.forEach((button) => {
            button.disabled = !enabled;
        });
    }

    isVisionModelSelected() {
        const selectedModel = this.view.getSelectedModel();
        const visionModels = Array.isArray(this.config.vision_models) ? this.config.vision_models : [];
        return visionModels.includes(selectedModel);
    }

    updateImageAttachmentUI() {
        const isVisionModel = this.isVisionModelSelected();
        attachImageButtonElem.classList.toggle('hidden', !isVisionModel);
        attachImageButtonElem.disabled = !isVisionModel;
        imageInputElem.disabled = !isVisionModel;

        if (!isVisionModel && this.pendingImages.length > 0) {
            this.clearPendingImages();
        }
    }

    updateSendButtonState() {
        const hasText = messageElem.value.trim().length > 0;
        const hasImages = this.isVisionModelSelected() && this.pendingImages.length > 0;
        const canSend = !this.isStreaming && (hasText || hasImages);

        if (canSend) {
            this.view.enableSend();
        } else {
            this.view.disableSend();
        }
    }

    renderPendingImages() {
        if (!this.pendingImages.length) {
            imagePreviewElem.innerHTML = '';
            imagePreviewElem.classList.add('hidden');
            return;
        }

        imagePreviewElem.classList.remove('hidden');
        imagePreviewElem.innerHTML = '';

        this.pendingImages.forEach((img) => {
            const item = document.createElement('div');
            item.className = 'image-preview-item';

            const thumbnail = document.createElement('img');
            thumbnail.className = 'image-preview-thumb';
            thumbnail.alt = img.name;
            thumbnail.src = img.dataUrl;
            thumbnail.addEventListener('click', () => {
                this.openImagePreviewModal(img.dataUrl, img.name);
            });

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'image-preview-remove';
            remove.title = `Remove ${img.name}`;
            remove.setAttribute('aria-label', `Remove ${img.name}`);
            remove.textContent = '×';
            remove.addEventListener('click', () => {
                this.pendingImages = this.pendingImages.filter((pending) => pending.id !== img.id);
                this.renderPendingImages();
                this.updateSendButtonState();
            });

            item.appendChild(thumbnail);
            item.appendChild(remove);
            imagePreviewElem.appendChild(item);
        });
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
        this.renderPendingImages();
        this.updateSendButtonState();
    }

    async handleImageSelection(files) {
        if (!this.isVisionModelSelected()) {
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
        this.renderPendingImages();
        this.updateSendButtonState();
    }

    wireUI() {
        sendButtonElem.addEventListener('click', async () => {
            await this.sendUserMessage();
        });

        messageElem.addEventListener('input', () => {
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
            if (!this.isVisionModelSelected()) {
                Flash.setMessage('The selected model does not support image inputs.', 'notice');
                return;
            }
            imageInputElem.click();
        });

        if (selectModelElem) {
            selectModelElem.addEventListener('change', () => {
                this.updateImageAttachmentUI();
                this.updateSendButtonState();
            });
        }

        imageInputElem.addEventListener('change', async (event) => {
            await this.handleImageSelection(event.target.files);
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
        const hasImages = this.isVisionModelSelected() && this.pendingImages.length > 0;
        return !!(this.isStreaming === false && (userMessage || hasImages));
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
            const images = this.isVisionModelSelected()
                ? this.pendingImages.map((img) => ({ data_url: img.dataUrl }))
                : [];
            if (!this.validateUserMessage(userMessage)) return;
            const message = { role: 'user', content: userMessage, images: images };
            const messageTextForStorage = userMessage || `[${images.length} image${images.length > 1 ? 's' : ''} attached]`;

            if (!this.dialogId) {
                const title = userMessage || `Image message (${images.length})`;
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
                        });
                    }
                }
            }

            const userMessageId = await this.storage.createMessage(this.dialogId, {
                role: 'user',
                content: messageTextForStorage,
                model: this.view.getSelectedModel(),
                images,
            });

            this.messages.push({ ...message, message_id: userMessageId });

            this.view.clearInput();
            this.clearPendingImages();

            const userContainer = this.view.renderStaticUserMessage(
                messageTextForStorage,
                userMessageId,
                async (id, newContent, container) => {
                    await this.handleMessageUpdate(id, newContent, container);
                },
                images,
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

        const assistantSegments = [];
        const turnEvents = [];
        const turnId = this.createTurnId();
        let turnUi = null;
        const hasVisibleText = (rawText) => String(rawText || '').trim().length > 0;

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

        const finalizeAssistantContainer = async () => {
            if (!turnUi) return;
            const finalized = await turnUi.finalizeAssistantSegment();
            if (!finalized) return;
            const segmentKind = String(finalized?.segmentKind || '').toLowerCase();
            const displayText = String(finalized?.displayText || '');

            if (!hasVisibleText(displayText)) {
                finalized.container.remove();
                return;
            }

            if (segmentKind === 'answer') {
                assistantSegments.push({
                    message: { role: 'assistant', content: displayText },
                    container: finalized.container,
                });
                turnEvents.push({
                    event_type: 'assistant_segment',
                    reasoning_text: '',
                    content_text: displayText,
                });
                return;
            }

            if (segmentKind === 'thinking') {
                turnEvents.push({
                    event_type: 'assistant_segment',
                    reasoning_text: displayText,
                    content_text: '',
                });
                return;
            }

            finalized.container.remove();
        };

        try {
            for await (const chunk of this.chat.stream({
                model: this.view.getSelectedModel(),
                dialog_id: this.dialogId || '',
                messages: this.messages,
            }, this.abortController.signal)) {
                if (chunk.toolStatus) {
                    const activeUi = await ensureAssistantContainer('Thinking', { showLoader: true });
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
                    turnEvents.push({
                        event_type: 'tool_call',
                        tool_call_id: String(chunk.toolCall.tool_call_id || ''),
                        tool_name: String(chunk.toolCall.tool_name || ''),
                        arguments_json: String(chunk.toolCall.arguments_json || '{}'),
                        result_text: String(chunk.toolCall.content || ''),
                        error_text: String(chunk.toolCall.error_text || ''),
                    });
                    continue;
                }

                if (chunk.reasoningOpenClose || chunk.reasoning) {
                    const activeUi = await ensureAssistantContainer('Thinking');
                    activeUi.setLoading(false);
                    activeUi.clearStatus();
                    if (chunk.reasoning) {
                        await activeUi.appendText(chunk.reasoning);
                    }
                }

                if (chunk.content) {
                    const activeUi = await ensureAssistantContainer('Answer');
                    activeUi.setLoading(false);
                    activeUi.clearStatus();
                    await activeUi.appendText(chunk.content, Boolean(chunk.done));
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

            if (this.dialogId && turnEvents.length > 0) {
                await this.storage.createAssistantTurnEvents(this.dialogId, {
                    turn_id: turnId,
                    events: turnEvents,
                });
            }

            for (const segment of assistantSegments) {
                this.messages.push(segment.message);
            }
            if (turnUi) {
                const liveTurnContainer = turnUi.container;
                if (turnEvents.length > 0) {
                    await this.view.renderStaticAssistantTurn(turnEvents, liveTurnContainer);
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
                promptRole === 'system' ? 'System' : 'User',
            );
            await this.view.scrollMessageToTop(promptContainer);

            this.messages = [{ role: promptRole, content: promptText, images: [] }];

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
