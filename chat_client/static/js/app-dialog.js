import { Requests } from '/static/js/requests.js';

async function getConfig() {
    return await Requests.asyncGetJson('/chat/config');
}

/**
 * Send user message to the server
 * Dialog starts with a placeholder title and can be renamed later
 * POST 'title' to '/chat/dialogs'
 */
async function createDialog(title) {

    const data = await Requests.asyncPostJson('/chat/dialogs', { title: title });

    if (data.error) {
        throw new Error(data.message);
    }

    const currentDialogID = data.dialog_id;
    console.log('Created dialog with ID:', currentDialogID);
    const url = new URL(window.location.href);
    url.pathname = `/chat/${currentDialogID}`
    window.history.replaceState({}, "", url);
    return currentDialogID

}

async function generateDialogTitle(dialogID) {
    const data = await Requests.asyncPostJson(`/chat/dialogs/${dialogID}/title`, {});

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

/**
 * Get messages connected to a dialog_id
 * /chat/dialogs/{dialog_id}/messages
 */
async function getMessages(dialogID) {

    const data = await Requests.asyncGetJson(`/chat/dialogs/${dialogID}/messages`);
    console.log(data)

    if (data.error) {
        throw new Error(data.message);
    }

    return data

}

/**
 * POST message object ({ role: role, message: message } ) to /chat/dialogs/{dialog_id}/messages
 * Returns the message_id of the created message
 */
async function createMessage(dialogID, message) {

    console.log('Creating message:', message);
    const data = await Requests.asyncPostJson(`/chat/dialogs/${dialogID}/messages`, message);

    if (data.error) {
        throw new Error(data.message);
    }

    return data.message_id;
}

async function createAssistantTurnEvents(dialogID, payload) {
    const data = await Requests.asyncPostJson(`/chat/dialogs/${dialogID}/assistant-turn-events`, payload);

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

async function uploadAttachment(file) {
    const formData = new FormData();
    formData.append('file', file);
    const data = await Requests.asyncPost('/chat/attachments', formData);

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

/**
 * Update message content
 * POST updated content to /chat/messages/{message_id}
 */
async function updateMessage(messageId, content) {
    console.log('Updating message:', messageId, content);
    const data = await Requests.asyncPostJson(`/chat/messages/${messageId}`, { content: content });

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

export { createDialog, generateDialogTitle, getMessages, createMessage, createAssistantTurnEvents, getConfig, updateMessage, uploadAttachment };
