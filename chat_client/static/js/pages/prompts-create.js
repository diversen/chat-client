import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';
import { initPromptFormPage } from '/static/js/pages/page-utils.js';

function initPromptsCreatePage() {
    initPromptFormPage({
        buttonId: 'create-btn',
        getSubmitUrl: () => '/api/prompts',
        requests: Requests,
        flash: Flash,
    });
}

export { initPromptsCreatePage };
