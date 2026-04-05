import { Requests } from '/static/js/requests.js';
import { Flash } from '/static/js/flash.js';
import { buildFormData, initFormSubmissionPage } from '/static/js/pages/page-utils.js';

function initUsersVerifyPage() {
    initFormSubmissionPage({
        buttonId: 'submit',
        request: async () => {
            const formData = buildFormData('signup-form');
            const response = await Requests.asyncPost('/user/verify', formData);
            return response;
        },
        onSuccess: (response) => {
            Flash.storeMessageForNextPage(response.message, 'success');
            window.location.href = '/user/login';
        },
        onError: (error) => {
            Flash.setMessageFromError(error, 'An error occurred while verifying your account. Try again later.');
        },
    });
}

export { initUsersVerifyPage };
