import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initUsersProfilePage() {
    const saveButton = document.getElementById('save');
    if (!saveButton) {
        return;
    }

    saveButton.addEventListener('click', async (event) => {
        event.preventDefault();

        const spinner = document.querySelector('.loading-spinner');
        spinner.classList.remove('hidden');

        try {
            const jsonData = {
                username: document.getElementById('username')?.value,
                dark_theme: document.getElementById('dark_theme')?.checked,
            };

            await Requests.asyncPostJson('/user/profile', jsonData);
            window.location.reload();
        } catch (error) {
            console.error(error);
            Flash.setMessage(
                Requests.getErrorMessage(error, 'An error occurred while saving your profile.'),
                'error',
            );
        } finally {
            spinner.classList.add('hidden');
        }
    });
}

export { initUsersProfilePage };
