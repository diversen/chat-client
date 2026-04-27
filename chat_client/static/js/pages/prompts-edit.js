import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';
import { initPromptFormPage } from '/static/js/pages/page-utils.js';

function initPromptsEditPage() {
    const editForm = document.getElementById('edit-form');
    initPromptFormPage({
        buttonId: 'save-btn',
        promptRecordId: editForm.getAttribute('data-prompt-id'),
        getSubmitUrl: ({ promptRecordId }) => {
            if (!promptRecordId) {
                Flash.setMessage('Prompt ID is missing.', 'error');
                return '';
            }
            return `/api/prompts/${promptRecordId}`;
        },
        onError: (error) => {
            Flash.setMessageFromError(error, 'An error occurred while updating the prompt.');
        },
        requests: Requests,
        flash: Flash,
    });
}

export { initPromptsEditPage };
