import {
    messageElem,
    selectModelElem,
    scrollToBottom,
    promptElem,
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

    function updateScrollToBottomPosition() {
        if (!scrollToBottom) return;
        const gapAbovePrompt = 12;
        const fallbackPromptHeight = 120;
        const promptHeight = promptElem
            ? Math.ceil(promptElem.getBoundingClientRect().height)
            : fallbackPromptHeight;
        scrollToBottom.style.bottom = `${promptHeight + gapAbovePrompt}px`;

        if (promptElem) {
            const promptRect = promptElem.getBoundingClientRect();
            const buttonWidth = Math.ceil(scrollToBottom.getBoundingClientRect().width) || 40;
            const maxLeft = Math.max(0, window.innerWidth - buttonWidth);
            const left = Math.round(promptRect.left + (promptRect.width - buttonWidth) / 2);
            scrollToBottom.style.right = 'auto';
            scrollToBottom.style.left = `${Math.min(Math.max(0, left), maxLeft)}px`;
        }
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
        updateScrollToBottomPosition();
    }

    window.addEventListener('load', applyInitialUIState);
    window.addEventListener('pageshow', applyInitialUIState);
    applyInitialUIState();
    window.addEventListener('resize', updateScrollToBottomPosition);

    if (promptElem && typeof ResizeObserver !== 'undefined') {
        const promptResizeObserver = new ResizeObserver(() => updateScrollToBottomPosition());
        promptResizeObserver.observe(promptElem);
    }

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
