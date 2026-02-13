import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initPromptsEditPage() {
    const saveButton = document.getElementById('save-btn');
    if (!saveButton) {
        return;
    }

    saveButton.addEventListener('click', async (event) => {
        event.preventDefault();

        const form = document.getElementById('edit-form');
        const promptId = form?.getAttribute('data-prompt-id');
        if (!promptId) {
            Flash.setMessage('Prompt ID is missing.', 'error');
            return;
        }

        const data = {
            title: document.getElementById('title')?.value,
            prompt: document.getElementById('prompt')?.value,
        };

        try {
            await Requests.asyncPostJson(`/prompt/${promptId}/edit`, data);
            window.location.href = '/prompt';
        } catch (error) {
            console.error(error);
            Flash.setMessage(
                Requests.getErrorMessage(error, 'An error occurred while updating the prompt.'),
                'error',
            );
        }
    });
}

export { initPromptsEditPage };
