import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';
import { initAsyncButtonAction } from '/static/js/pages/page-utils.js';

function initUsersProfilePage() {
    initAsyncButtonAction('save', async () => {
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
        }
    });
}

export { initUsersProfilePage };
