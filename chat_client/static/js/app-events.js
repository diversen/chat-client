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

function renderSelectedModelName({ selectModelElem, selectedModelNameElem }) {
    const selectedModel = String(selectModelElem.value || '').trim();
    selectedModelNameElem.textContent = selectedModel;
}

function applyInitialUIState({ messageElem, selectModelElem, selectedModelNameElem }) {
    const selectedModel = localStorage.getItem('selectedModel');
    if (selectedModel) {
        const modelOptions = Array.from(selectModelElem.options).map((option) => option.value);
        if (modelOptions.includes(selectedModel)) {
            selectModelElem.value = selectedModel;
        }
    }
    renderSelectedModelName({ selectModelElem, selectedModelNameElem });

    messageElem.style.display = 'unset';
    if (window.location.pathname === '/' || !isLikelyPhoneDevice()) {
        messageElem.focus();
    }
}

function initAppEvents({ messageElem, selectModelElem, selectedModelNameElem, scrollToBottom, promptElem }) {
    selectModelElem.addEventListener('change', () => {
        const selectedModel = selectModelElem.value;
        localStorage.setItem('selectedModel', selectedModel);
        renderSelectedModelName({ selectModelElem, selectedModelNameElem });
        messageElem.focus();
    });

    const updateScrollButtonLayout = () => updateScrollToBottomPosition({ scrollToBottom, promptElem });
    const initializeUI = () => {
        applyInitialUIState({ messageElem, selectModelElem, selectedModelNameElem });
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
