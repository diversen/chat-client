async function getConfig() {
    return await fetch('/config').then(response => response.json());
}

/**
 * Send user message to the server
 * Dialog title is based on first user message
 * POST 'title' to '/chat/create-dialog'
 */
async function createDialog(title) {

    const data = await fetch('/chat/create-dialog', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title }),
    }).then(response => response.json())

    if (data.error) {
        throw new Error(data.message);
    }

    const currentDialogID = data.dialog_id;
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

    const data = await fetch(`/chat/get-messages/${dialogID}`).then(response => response.json())
    console.log(data)

    if (data.error) {
        throw new Error(data.message);
    }

    return data

}

/**
 * POST message object ({ role: role, message: message } ) to /chat/create-message/{dialog_id}
 */
async function createMessage(dialogID, message) {

    console.log('Creating message:', message);
    const data = await fetch(`/chat/create-message/${dialogID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(message),
    }).then(response => response.json())

    if (data.error) {
        throw new Error(data.message);
    }

}

async function isLoggedInOrRedirect() {
    
    const data = await fetch('/user/is-logged-in').then(response => response.json());
    if (data.error) {
        window.location.href = data.redirect;
    }
}

export { createDialog, getMessages, createMessage, getConfig, isLoggedInOrRedirect };
