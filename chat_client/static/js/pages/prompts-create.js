import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';
import { getTrimmedValueById, validateRequiredFields } from '/static/js/pages/page-utils.js';

function initPromptsCreatePage() {
    const createButton = document.getElementById('create-btn');
    if (!createButton) {
        return;
    }

    createButton.addEventListener('click', async (event) => {
        event.preventDefault();

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
            await Requests.asyncPostJson('/prompt/create', data);
            window.location.href = '/prompt';
        } catch (error) {
            console.error(error);
            Flash.setMessage(Requests.getErrorMessage(error), 'error');
        }
    });
}

export { initPromptsCreatePage };
