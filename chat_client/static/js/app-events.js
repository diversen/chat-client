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

function shouldFocusMessageInput() {
    return window.location.pathname === '/' || !isLikelyPhoneDevice();
}

function initializeChatUI({ messageElem, modelSelection, reasoningSelection }) {
    modelSelection.restoreStoredModel();
    reasoningSelection.restoreStoredValue();
    modelSelection.render();
    modelSelection.bind();
    reasoningSelection.bind();
    messageElem.style.display = 'unset';
    if (shouldFocusMessageInput()) {
        messageElem.focus();
    }
}

function bindPromptFocusBehavior({ messageElem, modelSelection, reasoningSelection }) {
    modelSelection.subscribe(() => {
        messageElem.focus();
    });
    reasoningSelection.subscribe(() => {
        messageElem.focus();
    });
}

function bindScrollToBottomLayout({ scrollToBottom, promptElem }) {
    const updateScrollButtonLayout = () => updateScrollToBottomPosition({ scrollToBottom, promptElem });
    window.addEventListener('resize', updateScrollButtonLayout);

    if (typeof ResizeObserver !== 'undefined') {
        const promptResizeObserver = new ResizeObserver(updateScrollButtonLayout);
        promptResizeObserver.observe(promptElem);
    }

    return updateScrollButtonLayout;
}

function initAppEvents({ messageElem, scrollToBottom, promptElem, modelSelection, reasoningSelection }) {
    bindPromptFocusBehavior({ messageElem, modelSelection, reasoningSelection });
    const updateScrollButtonLayout = bindScrollToBottomLayout({ scrollToBottom, promptElem });
    const initializeUI = () => {
        initializeChatUI({ messageElem, modelSelection, reasoningSelection });
        updateScrollButtonLayout();
    };

    window.addEventListener('load', initializeUI);
    window.addEventListener('pageshow', initializeUI);
    initializeUI();
}

export { initAppEvents };
