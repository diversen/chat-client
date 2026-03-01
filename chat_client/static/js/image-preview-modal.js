function openImagePreviewModal(modalElem, imageElem, dataUrl, name) {
    if (!modalElem || !imageElem) {
        return;
    }
    imageElem.src = dataUrl;
    imageElem.alt = name || 'Selected image preview';
    modalElem.classList.remove('hidden');
}

function closeImagePreviewModal(modalElem, imageElem) {
    if (!modalElem || !imageElem) {
        return;
    }
    modalElem.classList.add('hidden');
    imageElem.src = '';
}

export {
    openImagePreviewModal,
    closeImagePreviewModal,
};
