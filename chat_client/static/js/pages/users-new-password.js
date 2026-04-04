import { Requests } from '/static/js/requests.js';
import { Flash } from '/static/js/flash.js';

function initUsersNewPasswordPage() {
    const submit = document.getElementById('submit');
    if (!submit) {
        return;
    }

    submit.addEventListener('click', async (event) => {
        event.preventDefault();

        const spinner = document.querySelector('.loading-spinner');
        spinner.classList.remove('hidden');

        try {
            const form = document.getElementById('new-password-form');
            const formData = new FormData(form);
            const response = await Requests.asyncPost('/user/password/new', formData);
            Flash.storeMessageForNextPage(response.message, 'success');
            window.location.replace('/user/login');
        } catch (error) {
            console.error(error);
            Flash.setMessageFromError(error, 'An error occurred while setting your new password. Try again later.');
        } finally {
            spinner.classList.add('hidden');
        }
    });
}

export { initUsersNewPasswordPage };
