import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initUsersLoginPage() {
    const loginButton = document.getElementById('login');
    if (!loginButton) {
        return;
    }

    loginButton.addEventListener('click', async (event) => {
        event.preventDefault();

        const spinner = document.querySelector('.loading-spinner');
        spinner.classList.remove('hidden');

        const jsonData = {
            email: document.getElementById('email')?.value,
            password: document.getElementById('password')?.value,
            remember: document.getElementById('remember')?.checked,
            next: new URL(window.location.href).searchParams.get('next') || '/',
        };

        try {
            const response = await Requests.asyncPostJson('/user/login', jsonData);
            window.location.href = response?.redirect || '/';
        } catch (error) {
            console.error(error);
            Flash.setMessageFromError(error, 'An error occurred while trying to log in. Try again later.');
        } finally {
            spinner.classList.add('hidden');
        }
    });
}

export { initUsersLoginPage };
