import {
    messageElem,
    selectModelElem,
    scrollToBottom,
} from '/static/js/app-elements.js';

function initAppEvents() {
    if (!messageElem) {
        return;
    }

    if (selectModelElem) {
        selectModelElem.addEventListener('change', () => {
            const selectedModel = selectModelElem.value;
            localStorage.setItem('selectedModel', selectedModel);
            messageElem.focus();
        });
    }

    function applyInitialUIState() {
        if (selectModelElem) {
            const selectedModel = localStorage.getItem('selectedModel');
            if (selectedModel) {
                const modelOptions = Array.from(selectModelElem.options).map((option) => option.value);
                if (modelOptions.includes(selectedModel)) {
                    selectModelElem.value = selectedModel;
                }
            }
            selectModelElem.style.display = 'block';
        }

        messageElem.style.display = 'unset';
        messageElem.focus();
    }

    window.addEventListener('load', applyInitialUIState);
    window.addEventListener('pageshow', applyInitialUIState);
    applyInitialUIState();

    if (scrollToBottom) {
        scrollToBottom.addEventListener('click', () => {
            window.scrollTo({
                top: document.documentElement.scrollHeight,
                behavior: 'smooth',
            });
        });
    }
}

export { initAppEvents };
