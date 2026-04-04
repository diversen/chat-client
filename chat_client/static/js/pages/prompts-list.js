import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initPromptsListPage() {
    const deleteButtons = document.querySelectorAll('.delete-btn');
    if (!deleteButtons.length) {
        return;
    }

    deleteButtons.forEach((btn) => {
        btn.addEventListener('click', async function (event) {
            event.preventDefault();
            const promptId = this.getAttribute('data-id');
            if (!promptId) {
                Flash.setMessage('Prompt ID is missing.', 'error');
                return;
            }

            if (!confirm('Are you sure you want to delete this prompt?')) {
                return;
            }

            try {
                const response = await Requests.asyncPostJson(`/prompt/${promptId}/delete`, {});
                Flash.storeMessageForNextPage(response.message, 'success');
                window.location.href = '/prompt';
            } catch (error) {
                console.error(error);
                Flash.setMessageFromError(error, 'An error occurred while deleting the prompt.');
            }
        });
    });
}

export { initPromptsListPage };
