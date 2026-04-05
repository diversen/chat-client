import { Requests } from '/static/js/requests.js';

async function getConfig() {
    return Requests.asyncGetJson('/api/chat/config');
}

/**
 * Send user message to the server
 * Dialog starts with a placeholder title and can be renamed later
 * POST 'title' to '/api/chat/dialogs'
 */
async function createDialog(title) {
    const data = await Requests.asyncPostJson('/api/chat/dialogs', { title });
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
    const { dialogId = '', pendingAttachmentIds = [] } = options;
    const formData = new FormData();
    formData.append('file', file);
    if (dialogId) {
        formData.append('dialog_id', dialogId);
    }
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

export { createDialog, generateDialogTitle, getMessages, createMessage, createAssistantTurnEvents, getConfig, updateMessage, uploadAttachment };
