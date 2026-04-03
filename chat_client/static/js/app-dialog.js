import { Requests } from '/static/js/requests.js';

async function getConfig() {
    return await Requests.asyncGetJson('/config');
}

/**
 * Send user message to the server
 * Dialog starts with a placeholder title and can be renamed later
 * POST 'title' to '/chat/create-dialog'
 */
async function createDialog(title) {

    const data = await Requests.asyncPostJson('/chat/create-dialog', { title: title });

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

async function generateDialogTitle(dialogID, payload) {
    const data = await Requests.asyncPostJson(`/chat/generate-dialog-title/${dialogID}`, payload);

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

/**
 * Get messages connected to a dialog_id
 * /chat/get-messages/{dialog_id}
 */
async function getMessages(dialogID) {

    const data = await Requests.asyncGetJson(`/chat/get-messages/${dialogID}`);
    console.log(data)

    if (data.error) {
        throw new Error(data.message);
    }

    return data

}

/**
 * POST message object ({ role: role, message: message } ) to /chat/create-message/{dialog_id}
 * Returns the message_id of the created message
 */
async function createMessage(dialogID, message) {

    console.log('Creating message:', message);
    const data = await Requests.asyncPostJson(`/chat/create-message/${dialogID}`, message);

    if (data.error) {
        throw new Error(data.message);
    }

    return data.message_id;
}

async function createAssistantTurnEvents(dialogID, payload) {
    const data = await Requests.asyncPostJson(`/chat/create-assistant-turn-events/${dialogID}`, payload);

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

async function uploadAttachment(file) {
    const formData = new FormData();
    formData.append('file', file);
    const data = await Requests.asyncPost('/chat/upload-attachment', formData);

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

async function isLoggedInOrRedirect() {
    
    const data = await Requests.asyncGetJson('/user/is-logged-in');
    if (data.error) {
        window.location.href = data.redirect;
    }
}

/**
 * Update message content
 * POST updated content to /chat/update-message/{message_id}
 */
async function updateMessage(messageId, content) {
    console.log('Updating message:', messageId, content);
    const data = await Requests.asyncPostJson(`/chat/update-message/${messageId}`, { content: content });

    if (data.error) {
        throw new Error(data.message);
    }

    return data;
}

export { createDialog, generateDialogTitle, getMessages, createMessage, createAssistantTurnEvents, getConfig, isLoggedInOrRedirect, updateMessage, uploadAttachment };
