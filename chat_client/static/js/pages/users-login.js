import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';
import { initAsyncButtonAction } from '/static/js/pages/page-utils.js';

function initUsersLoginPage() {
    initAsyncButtonAction('login', async () => {
        const emailElem = document.getElementById('email');
        const passwordElem = document.getElementById('password');
        const rememberElem = document.getElementById('remember');
        const jsonData = {
            email: emailElem.value,
            password: passwordElem.value,
            remember: rememberElem.checked,
            next: new URL(window.location.href).searchParams.get('next') || '/',
        };

        try {
            const response = await Requests.asyncPostJson('/user/login', jsonData);
            Flash.storeMessageForNextPage(response.message, 'success');
            window.location.href = response.redirect || '/';
        } catch (error) {
            console.error(error);
            Flash.setMessageFromError(error, 'An error occurred while trying to log in. Try again later.');
        }
    });
}

export { initUsersLoginPage };
