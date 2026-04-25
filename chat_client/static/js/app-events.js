function isLikelyPhoneDevice() {
    if (navigator.userAgentData && typeof navigator.userAgentData.mobile === 'boolean') {
        return navigator.userAgentData.mobile;
    }

    const userAgent = navigator.userAgent || '';
    return /(iPhone|iPod|Android.*Mobile|Windows Phone|Mobile)/i.test(userAgent);
}

function updateScrollToBottomPosition({ scrollToBottom, promptElem }) {
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

function applyInitialUIState({ messageElem, modelSelection }) {
    modelSelection.restoreStoredModel();
    modelSelection.render();
    modelSelection.bind();
    messageElem.style.display = 'unset';
    if (window.location.pathname === '/' || !isLikelyPhoneDevice()) {
        messageElem.focus();
    }
}

function initAppEvents({ messageElem, scrollToBottom, promptElem, modelSelection }) {
    modelSelection.subscribe(() => {
        messageElem.focus();
    });

    const updateScrollButtonLayout = () => updateScrollToBottomPosition({ scrollToBottom, promptElem });
    const initializeUI = () => {
        applyInitialUIState({ messageElem, modelSelection });
        updateScrollButtonLayout();
    };

    window.addEventListener('load', initializeUI);
    window.addEventListener('pageshow', initializeUI);
    initializeUI();
    window.addEventListener('resize', updateScrollButtonLayout);

    if (typeof ResizeObserver !== 'undefined') {
        const promptResizeObserver = new ResizeObserver(updateScrollButtonLayout);
        promptResizeObserver.observe(promptElem);
    }
}

export { initAppEvents };
