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
        spinner?.classList.remove('hidden');

        const jsonData = {
            email: document.getElementById('email')?.value,
            password: document.getElementById('password')?.value,
            remember: document.getElementById('remember')?.checked,
        };

        try {
            const res = await Requests.asyncPostJson('/user/login', jsonData);
            if (res.error) {
                Flash.setMessage(res.message, 'error');
            } else {
                window.location.href = '/';
            }
        } catch (error) {
            console.error(error);
            Flash.setMessage(error?.message || 'An error occurred while trying to log in. Try again later.', 'error');
        } finally {
            spinner?.classList.add('hidden');
        }
    });
}

export { initUsersLoginPage };
