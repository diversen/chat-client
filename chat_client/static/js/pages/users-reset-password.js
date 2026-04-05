import { Requests } from '/static/js/requests.js';
import { Flash } from '/static/js/flash.js';
import { buildFormData, initCaptcha, initFormSubmissionPage } from '/static/js/pages/page-utils.js';

function initUsersResetPasswordPage() {
    const submit = document.getElementById('submit');
    const captcha = document.getElementById('captcha-img');
    const captchaContainer = document.querySelector('.captcha-container');

    if (!submit || !initCaptcha(captcha, captchaContainer)) {
        return;
    }

    initFormSubmissionPage({
        buttonId: 'submit',
        request: async () => {
            const formData = buildFormData('reset-form');
            const response = await Requests.asyncPost('/user/password/reset', formData);
            return response;
        },
        onSuccess: (response) => {
            Flash.storeMessageForNextPage(response.message, 'success');
            window.location.replace('/user/login');
        },
        onError: (error) => {
            Flash.setMessageFromError(error, 'An error occurred while resetting your password. Try again later.');
        },
    });
}

export { initUsersResetPasswordPage };
