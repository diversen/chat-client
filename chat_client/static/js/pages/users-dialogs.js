import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initUsersDialogsPage() {
    const container = document.getElementById('dialogs-container');
    const loading = document.getElementById('loading');
    const noDialogs = document.getElementById('no-dialogs');

    if (!container || !loading || !noDialogs) {
        return;
    }

    let currentPage = 1;
    let isLoading = false;
    let hasMore = true;

    async function loadDialogs(page) {
        if (isLoading || !hasMore) return;

        isLoading = true;
        loading.classList.remove('hidden');

        try {
            const response = await Requests.asyncGetJson(`/user/dialogs/json?page=${page}`);
            if (response.error) {
                Flash.setMessage(response.message, 'error');
                return;
            }

            const info = response.dialogs_info;
            if (info.dialogs.length === 0 && currentPage === 1) {
                noDialogs.classList.remove('hidden');
                hasMore = false;
                return;
            }

            renderDialogs(info.dialogs);
            hasMore = info.has_next;
            currentPage += 1;
        } catch (error) {
            console.error(error);
            Flash.setMessage('An error occurred while loading dialogs.', 'error');
        } finally {
            isLoading = false;
            loading.classList.add('hidden');
        }
    }

    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function renderDialogs(dialogs) {
        for (const dialog of dialogs) {
            const html = `
                <div class="dialog">
                    <a href="/chat/${dialog.dialog_id}" class="delete svg-container" data-id="${dialog.dialog_id}">
                        <svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#e8eaed">
                            <path d="M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z" />
                        </svg>
                    </a>
                    <a href="/chat/${dialog.dialog_id}">${escapeHtml(dialog.title)}</a>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        }

        attachDeleteHandlers();
    }

    function attachDeleteHandlers() {
        document.querySelectorAll('.delete').forEach((elem) => {
            elem.removeEventListener('click', handleDelete);
            elem.addEventListener('click', handleDelete);
        });
    }

    async function handleDelete(event) {
        event.preventDefault();
        const elem = event.currentTarget;
        const dialogId = elem.getAttribute('data-id');

        loading.classList.remove('hidden');

        try {
            const response = await Requests.asyncPostJson(`/chat/delete-dialog/${dialogId}`, {});
            if (response.error) {
                Flash.setMessage(response.message, 'error');
            } else {
                const dialog = elem.closest('.dialog');
                dialog?.remove();
                Flash.setMessage('Dialog deleted successfully', 'success');
            }
        } catch (error) {
            console.error(error);
            Flash.setMessage('An error occurred while deleting the dialog.', 'error');
        } finally {
            loading.classList.add('hidden');
            handleScroll();
        }
    }

    function handleScroll() {
        if (isLoading || !hasMore) return;

        const dialogs = document.querySelectorAll('.dialog');
        if (!dialogs.length) return;

        const lastDialog = dialogs[dialogs.length - 1];
        const rect = lastDialog.getBoundingClientRect();

        if (rect.bottom <= window.innerHeight + 100) {
            loadDialogs(currentPage);
        }
    }

    function contentExceedsViewport() {
        const dialogs = document.querySelectorAll('.dialog');
        if (dialogs.length === 0) {
            return false;
        }

        const lastDialogRect = dialogs[dialogs.length - 1].getBoundingClientRect();
        return lastDialogRect.bottom > window.innerHeight;
    }

    async function initialLoadUntilFull() {
        while (hasMore && !contentExceedsViewport()) {
            await loadDialogs(currentPage);
        }
    }

    window.addEventListener('scroll', handleScroll);
    initialLoadUntilFull();
}

export { initUsersDialogsPage };
