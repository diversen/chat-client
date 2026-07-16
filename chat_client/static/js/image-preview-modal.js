const IMAGE_PREVIEW_HISTORY_KEY = '__chatClientImagePreview';

let activeModalElem = null;
let activeImageElem = null;
let historyEntryActive = false;
let historyWindow = null;

function hideImagePreviewModal(modalElem, imageElem) {
    modalElem.classList.add('hidden');
    imageElem.src = '';
}

function isImagePreviewHistoryState(state) {
    return Boolean(state && typeof state === 'object' && state[IMAGE_PREVIEW_HISTORY_KEY]);
}

function handleImagePreviewPopState() {
    if (!historyEntryActive) return;

    historyEntryActive = false;
    if (activeModalElem && activeImageElem) {
        hideImagePreviewModal(activeModalElem, activeImageElem);
    }
    activeModalElem = null;
    activeImageElem = null;
}

function ensureHistoryListener(windowObj) {
    if (historyWindow === windowObj) return;
    if (historyWindow) {
        historyWindow.removeEventListener('popstate', handleImagePreviewPopState);
    }
    historyWindow = windowObj;
    historyWindow.addEventListener('popstate', handleImagePreviewPopState);
}

function openImagePreviewModal(modalElem, imageElem, dataUrl, name) {
    if (!modalElem || !imageElem) {
        return;
    }
    const wasHidden = modalElem.classList.contains('hidden');
    imageElem.src = dataUrl;
    imageElem.alt = name || 'Selected image preview';
    modalElem.classList.remove('hidden');

    activeModalElem = modalElem;
    activeImageElem = imageElem;

    if (wasHidden && typeof window !== 'undefined' && window.history) {
        ensureHistoryListener(window);
        const currentState = window.history.state;
        const nextState = currentState && typeof currentState === 'object' && !Array.isArray(currentState)
            ? { ...currentState }
            : {};
        nextState[IMAGE_PREVIEW_HISTORY_KEY] = true;
        window.history.pushState(nextState, '', window.location.href);
        historyEntryActive = true;
    }
}

function closeImagePreviewModal(modalElem, imageElem) {
    if (!modalElem || !imageElem) {
        return;
    }
    const wasOpen = !modalElem.classList.contains('hidden');
    hideImagePreviewModal(modalElem, imageElem);

    if (wasOpen && historyEntryActive && historyWindow) {
        historyEntryActive = false;
        activeModalElem = null;
        activeImageElem = null;
        if (isImagePreviewHistoryState(historyWindow.history.state)) {
            historyWindow.history.back();
        }
    }
}

export {
    IMAGE_PREVIEW_HISTORY_KEY,
    openImagePreviewModal,
    closeImagePreviewModal,
    isImagePreviewHistoryState,
};
