function isLikelyPhoneDevice() {
    if (navigator.userAgentData && typeof navigator.userAgentData.mobile === 'boolean') {
        return navigator.userAgentData.mobile;
    }

    const userAgent = navigator.userAgent || '';
    return /(iPhone|iPod|Android.*Mobile|Windows Phone|Mobile)/i.test(userAgent);
}

function initAppEvents({ messageElem, selectModelElem, scrollToBottom, promptElem }) {

    selectModelElem.addEventListener('change', () => {
        const selectedModel = selectModelElem.value;
        localStorage.setItem('selectedModel', selectedModel);
        messageElem.focus();
    });

    function updateScrollToBottomPosition() {
        const gapAbovePrompt = 12;
        const promptHeight = Math.ceil(promptElem.getBoundingClientRect().height);
        scrollToBottom.style.bottom = `${promptHeight + gapAbovePrompt}px`;

        const promptRect = promptElem.getBoundingClientRect();
        const buttonWidth = Math.ceil(scrollToBottom.getBoundingClientRect().width) || 40;
        const maxLeft = Math.max(0, window.innerWidth - buttonWidth);
        const left = Math.round(promptRect.left + (promptRect.width - buttonWidth) / 2);
        scrollToBottom.style.right = 'auto';
        scrollToBottom.style.left = `${Math.min(Math.max(0, left), maxLeft)}px`;
    }

    function applyInitialUIState() {
        const selectedModel = localStorage.getItem('selectedModel');
        if (selectedModel) {
            const modelOptions = Array.from(selectModelElem.options).map((option) => option.value);
            if (modelOptions.includes(selectedModel)) {
                selectModelElem.value = selectedModel;
            }
        }
        selectModelElem.style.display = 'block';

        messageElem.style.display = 'unset';
        if (window.location.pathname === '/' || !isLikelyPhoneDevice()) {
            messageElem.focus();
        }
        updateScrollToBottomPosition();
    }

    window.addEventListener('load', applyInitialUIState);
    window.addEventListener('pageshow', applyInitialUIState);
    applyInitialUIState();
    window.addEventListener('resize', updateScrollToBottomPosition);

    if (typeof ResizeObserver !== 'undefined') {
        const promptResizeObserver = new ResizeObserver(() => updateScrollToBottomPosition());
        promptResizeObserver.observe(promptElem);
    }

    scrollToBottom.addEventListener('click', () => {
        window.scrollTo({
            top: document.documentElement.scrollHeight,
            behavior: 'smooth',
        });
    });
}

export { initAppEvents };
