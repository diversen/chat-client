function getRequiredElement(selector, queryMethod = 'getElementById') {
    const element = queryMethod === 'querySelector'
        ? document.querySelector(selector)
        : document.getElementById(selector);

    if (!element) {
        throw new Error(`Missing required chat element: ${selector}`);
    }

    return element;
}
function getChatElements() {
    return {
        responsesElem: getRequiredElement('responses'),
        messageFormElem: getRequiredElement('message-form'),
        messageElem: getRequiredElement('message'),
        sendButtonElem: getRequiredElement('send'),
        newButtonElem: getRequiredElement('new'),
        abortButtonElem: getRequiredElement('abort'),
        selectModelElem: getRequiredElement('select-model'),
        selectedModelNameElem: getRequiredElement('selected-model-name'),
        loadingSpinner: getRequiredElement('.loading-spinner', 'querySelector'),
        scrollToBottom: getRequiredElement('scroll-to-bottom'),
        promptElem: getRequiredElement('prompt'),
        imageInputElem: getRequiredElement('image-input'),
        pendingUploadsElem: getRequiredElement('pending-uploads'),
        attachImageButtonElem: getRequiredElement('attach-image'),
        attachmentInputElem: getRequiredElement('attachment-input'),
        attachFileButtonElem: getRequiredElement('attach-file'),
        modelPickerDisplayElem: getRequiredElement('.model-picker-display', 'querySelector'),
        imagePreviewModalElem: getRequiredElement('image-preview-modal'),
        imagePreviewModalImageElem: getRequiredElement('image-preview-modal-image'),
        imagePreviewModalCloseElem: getRequiredElement('image-preview-modal-close'),
    };
}

export { getChatElements };
