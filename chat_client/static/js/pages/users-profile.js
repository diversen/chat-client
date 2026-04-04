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
                username: document.getElementById('username').value,
                theme_preference: document.getElementById('theme_preference').value,
            };

            const response = await Requests.asyncPostJson('/api/user/profile', jsonData);
            Flash.storeMessageForNextPage(response.message, 'success');
            window.location.reload();
        } catch (error) {
            console.error(error);
            Flash.setMessageFromError(error, 'An error occurred while saving your profile.');
        } finally {
            spinner.classList.add('hidden');
        }
    });
}

export { initUsersProfilePage };
