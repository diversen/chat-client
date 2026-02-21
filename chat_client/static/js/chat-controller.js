import { Flash } from './flash.js';
import { logError } from './error-log.js';
import { addCopyButtons } from './app-copy-buttons.js';
import { Requests } from './requests.js';
import {
    responsesElem,
    messageElem,
    sendButtonElem,
    abortButtonElem,
    scrollToBottom,
    imageInputElem,
    imagePreviewElem,
    attachImageButtonElem,
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
        this.updateSendButtonState();
    }

    updateSendButtonState() {
        const hasText = messageElem.value.trim().length > 0;
        const hasImages = this.pendingImages.length > 0;
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
            remove.textContent = 'x';
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
        if (!imagePreviewModalElem || !imagePreviewModalImageElem) return;
        imagePreviewModalImageElem.src = dataUrl;
        imagePreviewModalImageElem.alt = name || 'Selected image preview';
        imagePreviewModalElem.classList.remove('hidden');
    }

    closeImagePreviewModal() {
        if (!imagePreviewModalElem || !imagePreviewModalImageElem) return;
        imagePreviewModalElem.classList.add('hidden');
        imagePreviewModalImageElem.src = '';
    }

    clearPendingImages() {
        this.pendingImages = [];
        imageInputElem.value = '';
        this.closeImagePreviewModal();
        this.renderPendingImages();
        this.updateSendButtonState();
    }

    async handleImageSelection(files) {
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

        attachImageButtonElem.addEventListener('click', () => {
            imageInputElem.click();
        });

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

        let userInteracting = false;
        let interactionTimeout;

        window.addEventListener('wheel', () => {
            userInteracting = true;
            if (scrollToBottom) {
                scrollToBottom.style.display = 'none';
            }
            clearTimeout(interactionTimeout);
            interactionTimeout = setTimeout(() => {
                userInteracting = false;
                this.checkScroll(userInteracting);
            }, 1000);
        });

        window.addEventListener('touchstart', (event) => {
            if (scrollToBottom && event.target instanceof Element && event.target.closest('#scroll-to-bottom')) {
                return;
            }
            userInteracting = true;
            if (scrollToBottom) {
                scrollToBottom.style.display = 'none';
            }
            clearTimeout(interactionTimeout);
        });

        window.addEventListener('touchend', () => {
            clearTimeout(interactionTimeout);
            interactionTimeout = setTimeout(() => {
                userInteracting = false;
                this.checkScroll(userInteracting);
            }, 1000);
        });

        window.addEventListener('scroll', () => this.checkScroll(userInteracting), { passive: true });
        new MutationObserver(() => this.checkScroll(userInteracting)).observe(responsesElem, { childList: true, subtree: true });
    }

    checkScroll(userInteracting) {
        if (!scrollToBottom) return;

        const threshold = 2;
        const doc = document.documentElement;
        const atBottom = Math.abs((window.innerHeight + window.scrollY) - doc.scrollHeight) <= threshold;
        const hasScrollbar = doc.scrollHeight > window.innerHeight;

        if (hasScrollbar && !atBottom && !userInteracting) {
            scrollToBottom.style.display = 'flex';
        } else {
            scrollToBottom.style.display = 'none';
        }
    }

    validateUserMessage(userMessage) {
        const hasImages = this.pendingImages.length > 0;
        return !!(this.isStreaming === false && (userMessage || hasImages));
    }

    async sendUserMessage() {
        try {
            await this.auth.ensure();
            const userMessage = messageElem.value.trim();
            const images = this.pendingImages.map((img) => ({ data_url: img.dataUrl }));
            if (!this.validateUserMessage(userMessage)) return;
            const message = { role: 'user', content: userMessage, images: images };
            const messageTextForStorage = userMessage || `[${images.length} image${images.length > 1 ? 's' : ''} attached]`;

            if (this.messages.length === 0) {
                const title = userMessage || `Image message (${images.length})`;
                this.dialogId = await this.storage.createDialog(title);
            }

            const userMessageId = await this.storage.createMessage(this.dialogId, {
                role: 'user',
                content: messageTextForStorage,
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
        await this.storage.updateMessage(messageId, newContent);

        const contentElement = container.querySelector('.content');
        contentElement.style.whiteSpace = 'pre-wrap';
        contentElement.innerText = newContent;

        this.view.hideEditForm(container);
        this.removeMessagesAfter(container);
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
        const ui = this.view.createAssistantContainer();
        this.view.disableNew();
        this.view.enableAbort();
        this.isStreaming = true;
        this.updateSendButtonState();

        try {
            for await (const chunk of this.chat.stream({
                model: this.view.getSelectedModel(),
                dialog_id: this.dialogId || '',
                messages: this.messages,
            }, this.abortController.signal)) {
                ui.loader.classList.add('hidden');

                if (chunk.reasoningOpenClose === 'open') ui.appendReasoning('');
                else if (chunk.reasoningOpenClose === 'close') ui.closeReasoningIfOpen();

                if (chunk.reasoning) await ui.appendContent(chunk.reasoning);
                if (chunk.content) await ui.appendContent(chunk.content, Boolean(chunk.done));
                if (this.config.show_mcp_tool_calls && chunk.toolCall) {
                    this.view.renderStaticToolMessage(chunk.toolCall, ui.container);
                }
                this.view.relaxAnchorSpacer();
            }
        } catch (error) {
            ui.loader.classList.add('hidden');
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
            this.view.disableAbort();
            this.view.enableNew();
            this.updateSendButtonState();

            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

            const finalText = await ui.finalize();
            await addCopyButtons(ui.contentElement, this.config);

            const assistantMessage = { role: 'assistant', content: finalText };
            const assistantMessageId = await this.storage.createMessage(this.dialogId, assistantMessage);

            ui.container.setAttribute('data-message-id', assistantMessageId);
            this.view.attachCopy(ui.container, finalText);

            this.messages.push({ ...assistantMessage, message_id: assistantMessageId });
            this.abortController = new AbortController();
            this.view.clearAnchorSpacer();
        }
    }

    async loadDialog(savedMessages) {
        this.messages = savedMessages.filter((msg) => msg.role === 'user' || msg.role === 'assistant');
        responsesElem.innerHTML = '';

        for (const msg of savedMessages) {
            if (msg.role === 'user') {
                this.view.renderStaticUserMessage(
                    msg.content,
                    msg.message_id,
                    async (id, newContent, container) => {
                        await this.handleMessageUpdate(id, newContent, container);
                    },
                    msg.images || [],
                );
            } else if (msg.role === 'tool' && this.config.show_mcp_tool_calls) {
                this.view.renderStaticToolMessage(msg);
            } else {
                await this.view.renderStaticAssistantMessage(msg.content, msg.message_id);
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

            this.dialogId = await this.storage.createDialog(promptText);
            await this.storage.createMessage(this.dialogId, { role: 'user', content: promptText });
            window.history.replaceState({}, document.title, `/chat/${this.dialogId}`);
            await this.initializeDialog(this.dialogId);
        } catch (error) {
            console.error('Error in initializeFromPrompt:', error);
            Flash.setMessage('An error occurred while initializing from prompt.', 'error');
        }
    }
}

export { ConversationController };
