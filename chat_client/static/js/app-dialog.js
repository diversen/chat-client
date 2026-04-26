import { Requests } from '/static/js/requests.js';

async function getConfig() {
    return Requests.asyncGetJson('/api/chat/config');
}

/**
 * Create a dialog. The server can derive the initial title from the first user message.
 */
async function createDialog(title, initialMessage = '') {
    const data = await Requests.asyncPostJson('/api/chat/dialogs', { title, initial_message: initialMessage });
    const currentDialogID = data.dialog_id;
    const url = new URL(window.location.href);
    url.pathname = `/chat/${currentDialogID}`;
    window.history.replaceState({}, '', url);
    return currentDialogID;
}

async function generateDialogTitle(dialogID) {
    return Requests.asyncPostJson(`/api/chat/dialogs/${dialogID}/title`, {});
}

/**
 * Get messages connected to a dialog_id
 * /api/chat/dialogs/{dialog_id}/messages
 */
async function getMessages(dialogID) {
    return Requests.asyncGetJson(`/api/chat/dialogs/${dialogID}/messages`);
}

async function getDialogUsage(dialogID) {
    return Requests.asyncGetJson(`/api/chat/dialogs/${dialogID}/usage`);
}

/**
 * POST message object ({ role: role, message: message } ) to /api/chat/dialogs/{dialog_id}/messages
 * Returns the message_id of the created message
 */
async function createMessage(dialogID, message) {
    const data = await Requests.asyncPostJson(`/api/chat/dialogs/${dialogID}/messages`, message);
    return data.message_id;
}

async function createAssistantTurnEvents(dialogID, payload) {
    return Requests.asyncPostJson(`/api/chat/dialogs/${dialogID}/assistant-turn-events`, payload);
}

async function uploadAttachment(file, options = {}) {
    const { dialogId = '', pendingAttachmentIds = [], pendingImageCount = 0 } = options;
    const formData = new FormData();
    formData.append('file', file);
    if (dialogId) {
        formData.append('dialog_id', dialogId);
    }
    formData.append('pending_image_count', String(pendingImageCount));
    pendingAttachmentIds.forEach((attachmentId) => {
        formData.append('pending_attachment_ids', String(attachmentId));
    });
    return Requests.asyncPost('/api/chat/attachments', formData);
}

/**
 * Update message content
 * POST updated content to /api/chat/messages/{message_id}
 */
async function updateMessage(messageId, content) {
    return Requests.asyncPostJson(`/api/chat/messages/${messageId}`, { content });
}

export { createDialog, generateDialogTitle, getMessages, getDialogUsage, createMessage, createAssistantTurnEvents, getConfig, updateMessage, uploadAttachment };
