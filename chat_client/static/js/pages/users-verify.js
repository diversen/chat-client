import { Requests } from '/static/js/requests.js';
import { Flash } from '/static/js/flash.js';

function initUsersVerifyPage() {
    const submit = document.getElementById('submit');
    if (!submit) {
        return;
    }

    submit.addEventListener('click', async (event) => {
        event.preventDefault();

        const spinner = document.querySelector('.loading-spinner');
        spinner?.classList.remove('hidden');

        try {
            const form = document.getElementById('signup-form');
            const formData = new FormData(form);
            await Requests.asyncPost('/user/verify', formData);
            window.location.href = '/user/login';
        } catch (error) {
            console.error(error);
            Flash.setMessage(
                Requests.getErrorMessage(error, 'An error occurred while verifying your account. Try again later.'),
                'error',
            );
        } finally {
            spinner?.classList.add('hidden');
        }
    });
}

export { initUsersVerifyPage };
