import { Requests } from '/static/js/requests.js';
import { Flash } from '/static/js/flash.js';

function initUsersResetPasswordPage() {
    const submit = document.getElementById('submit');
    const captcha = document.getElementById('captcha-img');
    const captchaContainer = document.querySelector('.captcha-container');

    if (!submit || !captcha || !captchaContainer) {
        return;
    }

    captcha.addEventListener('click', () => {
        captcha.src = `/captcha?${Math.random()}`;
    });

    captcha.src = `/captcha?${Math.random()}`;
    captchaContainer.classList.remove('hidden');

    submit.addEventListener('click', async (event) => {
        event.preventDefault();

        const spinner = document.querySelector('.loading-spinner');
        spinner.classList.remove('hidden');

        try {
            const form = document.getElementById('reset-form');
            const formData = new FormData(form);
            await Requests.asyncPost('/user/reset', formData);
            window.location.replace('/user/login');
        } catch (error) {
            console.error(error);
            Flash.setMessage(
                Requests.getErrorMessage(error, 'An error occurred while resetting your password. Try again later.'),
                'error',
            );
        } finally {
            spinner.classList.add('hidden');
        }
    });
}

export { initUsersResetPasswordPage };
