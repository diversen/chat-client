import { Flash } from '/static/js/flash.js';
import { Requests } from '/static/js/requests.js';

function initUsersDialogsPage() {
    const container = document.getElementById('dialogs-container');
    const loading = document.getElementById('loading');
    const loadMoreButton = document.getElementById('load-more-dialogs');
    const noDialogs = document.getElementById('no-dialogs');
    const searchForm = document.getElementById('dialogs-search-form');
    const searchInput = document.getElementById('dialogs-search-input');

    if (!container || !loading || !loadMoreButton || !noDialogs || !searchForm || !searchInput) {
        return;
    }

    const url = new URL(window.location.href);
    let currentPage = 1;
    let isLoading = false;
    let hasMore = true;
    let currentQuery = String(url.searchParams.get('q') || '').trim();
    let searchTimer = null;

    searchInput.value = currentQuery;

    function syncQueryInUrl(query) {
        const nextUrl = new URL(window.location.href);
        if (query) {
            nextUrl.searchParams.set('q', query);
        } else {
            nextUrl.searchParams.delete('q');
        }
        window.history.replaceState({}, document.title, `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`);
    }

    function getDialogHref(dialogId) {
        const hrefUrl = new URL(`/chat/${dialogId}`, window.location.origin);
        if (currentQuery) {
            hrefUrl.searchParams.set('q', currentQuery);
        }
        return `${hrefUrl.pathname}${hrefUrl.search}`;
    }

    async function loadDialogs(page) {
        if (isLoading || !hasMore) return;

        isLoading = true;
        loading.classList.remove('hidden');
        loadMoreButton.disabled = true;

        try {
            const response = await Requests.asyncGetJson(`/user/dialogs/json?page=${page}&q=${encodeURIComponent(currentQuery)}`);
            const info = response.dialogs_info;
            if (info.dialogs.length === 0 && currentPage === 1) {
                noDialogs.classList.remove('hidden');
                hasMore = false;
                loadMoreButton.classList.add('hidden');
                return;
            }

            noDialogs.classList.add('hidden');
            renderDialogs(info.dialogs);
            hasMore = info.has_next;
            currentPage += 1;
            if (hasMore) {
                loadMoreButton.classList.remove('hidden');
            } else {
                loadMoreButton.classList.add('hidden');
            }
        } catch (error) {
            console.error(error);
            Flash.setMessage(Requests.getErrorMessage(error, 'An error occurred while loading dialogs.'), 'error');
        } finally {
            isLoading = false;
            loadMoreButton.disabled = false;
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
            const dialogHref = getDialogHref(dialog.dialog_id);
            const html = `
                <div class="dialog">
                    <a href="${dialogHref}" class="delete svg-container" data-id="${dialog.dialog_id}">
                        <svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#e8eaed">
                            <path d="M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z" />
                        </svg>
                    </a>
                    <a href="${dialogHref}">${escapeHtml(dialog.title)}</a>
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
            await Requests.asyncPostJson(`/chat/delete-dialog/${dialogId}`, {});
            const dialog = elem.closest('.dialog');
            dialog?.remove();
            if (container.querySelectorAll('.dialog').length === 0 && !hasMore) {
                noDialogs.classList.remove('hidden');
            }
            Flash.setMessage('Dialog deleted successfully', 'success');
        } catch (error) {
            console.error(error);
            Flash.setMessage(Requests.getErrorMessage(error, 'An error occurred while deleting the dialog.'), 'error');
        } finally {
            loading.classList.add('hidden');
        }
    }

    function resetAndLoad(query) {
        const nextQuery = String(query || '').trim();
        if (nextQuery === currentQuery && container.children.length > 0) {
            return;
        }
        currentQuery = nextQuery;
        syncQueryInUrl(currentQuery);
        currentPage = 1;
        hasMore = true;
        container.innerHTML = '';
        noDialogs.classList.add('hidden');
        loadMoreButton.classList.add('hidden');
        loadDialogs(currentPage);
    }

    window.addEventListener('popstate', () => {
        const params = new URL(window.location.href).searchParams;
        const queryFromUrl = String(params.get('q') || '').trim();
        searchInput.value = queryFromUrl;
        resetAndLoad(queryFromUrl);
    });

    searchForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (searchTimer) {
            clearTimeout(searchTimer);
            searchTimer = null;
        }
        resetAndLoad(searchInput.value);
    });
    searchInput.addEventListener('input', () => {
        if (searchTimer) {
            clearTimeout(searchTimer);
        }
        searchTimer = setTimeout(() => {
            resetAndLoad(searchInput.value);
        }, 500);
    });

    loadMoreButton.addEventListener('click', () => {
        loadDialogs(currentPage);
    });
    resetAndLoad(currentQuery);
}

export { initUsersDialogsPage };
