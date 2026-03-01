import { Requests } from '/static/js/requests.js';
import { Flash } from '/static/js/flash.js';
import { initCaptcha, runWithSpinner } from '/static/js/pages/page-utils.js';

function initUsersSignupPage() {
    const submit = document.getElementById('submit');
    const captcha = document.getElementById('captcha-img');
    const captchaContainer = document.querySelector('.captcha-container');

    if (!submit || !initCaptcha(captcha, captchaContainer)) {
        return;
    }

    submit.addEventListener('click', async (event) => {
        event.preventDefault();
        await runWithSpinner(async () => {
            try {
                const form = document.getElementById('signup-form');
                const formData = new FormData(form);
                await Requests.asyncPost('/user/signup', formData);
                window.location.replace('/user/login');
            } catch (error) {
                console.error(error);
                Flash.setMessage(
                    Requests.getErrorMessage(error, 'An error occurred while creating your account. Try again later.'),
                    'error',
                );
            }
        });
    });
}

export { initUsersSignupPage };
