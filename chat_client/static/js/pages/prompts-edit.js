import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';
import { getTrimmedValueById, validateRequiredFields } from '/static/js/pages/page-utils.js';

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

        const title = getTrimmedValueById('title');
        const prompt = getTrimmedValueById('custom-prompt');

        const isValid = validateRequiredFields(
            [
                { value: title, message: 'Please enter a title.' },
                { value: prompt, message: 'Please enter a prompt.' },
            ],
            (message) => Flash.setMessage(message, 'error'),
        );
        if (!isValid) {
            return;
        }

        const data = {
            title,
            prompt,
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
