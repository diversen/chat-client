import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initPromptsDetailPage() {
    const deleteButton = document.getElementById('delete-btn');
    if (!deleteButton) {
        return;
    }

    deleteButton.addEventListener('click', async () => {
        const promptId = deleteButton.getAttribute('data-prompt-id');
        if (!promptId) {
            Flash.setMessage('Prompt ID is missing.', 'error');
            return;
        }

        if (!confirm('Are you sure you want to delete this prompt?')) {
            return;
        }

        try {
            await Requests.asyncPostJson(`/prompt/${promptId}/delete`, {});
            window.location.href = '/prompt';
        } catch (error) {
            console.error(error);
            Flash.setMessage(
                Requests.getErrorMessage(error, 'An error occurred while deleting the prompt.'),
                'error',
            );
        }
    });
}

export { initPromptsDetailPage };
