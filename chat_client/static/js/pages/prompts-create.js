import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initPromptsCreatePage() {
    const createButton = document.getElementById('create-btn');
    if (!createButton) {
        return;
    }

    createButton.addEventListener('click', async (event) => {
        event.preventDefault();

        const data = {
            title: document.getElementById('title')?.value,
            prompt: document.getElementById('prompt')?.value,
        };

        try {
            const res = await Requests.asyncPostJson('/prompt/create', data);
            if (res.error) {
                Flash.setMessage(res.message, 'error');
            } else {
                window.location.href = '/prompt';
            }
        } catch (error) {
            console.error(error);
            Flash.setMessage('An error occurred. Try again later.', 'error');
        }
    });
}

export { initPromptsCreatePage };
