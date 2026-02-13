import {
    responsesElem,
    messageElem,
    sendButtonElem,
    selectModelElem,
    chatContainer,
    scrollToBottom,
} from '/static/js/app-elements.js';

function initAppEvents() {
    if (!messageElem || !sendButtonElem) {
        return;
    }

    sendButtonElem.setAttribute('disabled', true);

    function updateSendButtonState() {
        const hasText = messageElem.value.trim().length > 0;
        const hasImages = messageElem.dataset.hasImages === '1';
        if (hasText || hasImages) {
            sendButtonElem.removeAttribute('disabled');
        } else {
            sendButtonElem.setAttribute('disabled', true);
        }
    }

    messageElem.addEventListener('input', () => {
        updateSendButtonState();
    });

    document.addEventListener('chat:images-updated', updateSendButtonState);

    if (selectModelElem) {
        selectModelElem.addEventListener('change', () => {
            const selectedModel = selectModelElem.value;
            localStorage.setItem('selectedModel', selectedModel);
            messageElem.focus();
        });
    }

    function setChatContainerHeight() {
        if (!chatContainer) {
            return;
        }
        const visibleHeight = window.innerHeight;
        const headerHeight = 0;
        const chatContainerHeight = visibleHeight - headerHeight;
        chatContainer.style.height = `${chatContainerHeight}px`;
    }

    function applyInitialUIState() {
        setChatContainerHeight();

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

    window.addEventListener('resize', () => {
        setChatContainerHeight();
    });

    if (scrollToBottom && responsesElem) {
        scrollToBottom.addEventListener('click', () => {
            responsesElem.scrollTo({
                top: responsesElem.scrollHeight,
                behavior: 'smooth',
            });
        });
    }
}

export { initAppEvents };
