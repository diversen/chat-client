import { Requests } from '/static/js/requests.js';
import { Flash } from '/static/js/flash.js';
import { buildFormData, initFormSubmissionPage } from '/static/js/pages/page-utils.js';

function initUsersNewPasswordPage() {
    initFormSubmissionPage({
        buttonId: 'submit',
        request: async () => {
            const formData = buildFormData('new-password-form');
            const response = await Requests.asyncPost('/user/password/new', formData);
            return response;
        },
        onSuccess: (response) => {
            Flash.storeMessageForNextPage(response.message, 'success');
            window.location.replace('/user/login');
        },
        onError: (error) => {
            Flash.setMessageFromError(error, 'An error occurred while setting your new password. Try again later.');
        },
    });
}

export { initUsersNewPasswordPage };
