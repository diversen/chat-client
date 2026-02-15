import { Requests } from '/static/js/requests.js';

async function getConfig() {
    return await Requests.asyncGetJson('/config');
}

/**
 * Send user message to the server
 * Dialog title is based on first user message
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

export { createDialog, getMessages, createMessage, getConfig, isLoggedInOrRedirect, updateMessage };
