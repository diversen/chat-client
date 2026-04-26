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

    function createDeleteIcon() {
        const svgNamespace = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(svgNamespace, 'svg');
        svg.setAttribute('xmlns', svgNamespace);
        svg.setAttribute('height', '24px');
        svg.setAttribute('viewBox', '0 -960 960 960');
        svg.setAttribute('width', '24px');
        svg.setAttribute('fill', '#e8eaed');

        const path = document.createElementNS(svgNamespace, 'path');
        path.setAttribute(
            'd',
            'M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z',
        );
        svg.appendChild(path);
        return svg;
    }

    function createDialogElement(dialog) {
        const dialogElem = document.createElement('div');
        dialogElem.className = 'dialog';

        const dialogHref = getDialogHref(dialog.dialog_id);

        const deleteLink = document.createElement('a');
        deleteLink.href = dialogHref;
        deleteLink.className = 'delete svg-container';
        deleteLink.dataset.id = String(dialog.dialog_id);
        deleteLink.appendChild(createDeleteIcon());

        const titleLink = document.createElement('a');
        titleLink.href = dialogHref;
        titleLink.textContent = String(dialog.title || '');

        dialogElem.appendChild(deleteLink);
        dialogElem.appendChild(titleLink);
        return dialogElem;
    }

    async function loadDialogs(page) {
        if (isLoading || !hasMore) return;

        isLoading = true;
        loading.classList.remove('hidden');
        loadMoreButton.disabled = true;

        try {
            const response = await Requests.asyncGetJson(`/api/user/dialogs?page=${page}&q=${encodeURIComponent(currentQuery)}`);
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
            Flash.setMessageFromError(error, 'An error occurred while loading dialogs.');
        } finally {
            isLoading = false;
            loadMoreButton.disabled = false;
            loading.classList.add('hidden');
        }
    }

    function renderDialogs(dialogs) {
        for (const dialog of dialogs) {
            container.appendChild(createDialogElement(dialog));
        }
    }

    async function handleDelete(elem) {
        const dialogId = elem.getAttribute('data-id');
        if (!dialogId) {
            Flash.setMessage('Dialog ID is missing.', 'error');
            return;
        }

        if (!confirm('Are you sure you want to delete this dialog?')) {
            return;
        }

        loading.classList.remove('hidden');

        try {
            await Requests.asyncPostJson(`/api/chat/dialogs/${dialogId}`, {});
            const dialog = elem.closest('.dialog');
            dialog?.remove();
            if (container.querySelectorAll('.dialog').length === 0 && !hasMore) {
                noDialogs.classList.remove('hidden');
            }
            Flash.setMessage('Dialog deleted successfully', 'success');
        } catch (error) {
            console.error(error);
            Flash.setMessageFromError(error, 'An error occurred while deleting the dialog.');
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

    container.addEventListener('click', async (event) => {
        const deleteLink = event.target.closest('.delete');
        if (!deleteLink || !container.contains(deleteLink)) {
            return;
        }

        event.preventDefault();
        await handleDelete(deleteLink);
    });

    loadMoreButton.addEventListener('click', () => {
        loadDialogs(currentPage);
    });
    resetAndLoad(currentQuery);
}

export { initUsersDialogsPage };
