import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initPromptsCreatePage() {
    const createButton = document.getElementById('create-btn');
    if (!createButton) {
        return;
    }

    createButton.addEventListener('click', async (event) => {
        event.preventDefault();

        const title = document.getElementById('title')?.value?.trim() || '';
        const prompt = document.getElementById('prompt')?.value?.trim() || '';

        if (!title) {
            Flash.setMessage('Please enter a title.', 'error');
            return;
        }
        if (!prompt) {
            Flash.setMessage('Please enter a prompt.', 'error');
            return;
        }

        const data = {
            title,
            prompt,
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
            Flash.setMessage(error?.message || 'An error occurred. Try again later.', 'error');
        }
    });
}

export { initPromptsCreatePage };
