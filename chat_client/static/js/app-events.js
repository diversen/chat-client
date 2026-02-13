import { responsesElem, messageElem, sendButtonElem, newButtonElem, abortButtonElem, selectModelElem, chatContainer, scrollToBottom } from '/static/js/app-elements.js';

// sendButtonElem is disabled by default
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

// Add event to sendButtonElem to remove disabled when content exists in messageElem
messageElem.addEventListener('input', () => {
    updateSendButtonState();
});

document.addEventListener('chat:images-updated', updateSendButtonState);

/**
 * On select model change save the selected model in local storage
 */
selectModelElem.addEventListener('change', () => {
    const selectedModel = selectModelElem.value;
    localStorage.setItem('selectedModel', selectedModel);

    // Focus on the message input when the model is changed
    messageElem.focus();
});


function setChatContainerHeight() {
    const visibleHeight = window.innerHeight;

    // Set chat container height to the visible height minus the header ( 61 px)
    const headerHeight = 0;
    const chatContainerHeight = visibleHeight - headerHeight;
    chatContainer.style.height = `${chatContainerHeight}px`;
}

/**
 * On page load, check if a model is saved in local storage and set it as the selected model
 */
window.addEventListener('load', () => {
    setChatContainerHeight();
    let selectedModel = localStorage.getItem('selectedModel');
    if (selectedModel) {

        // Check if the selected model is in the list of available models
        const modelOptions = Array.from(selectModelElem.options).map(option => option.value);
        if (modelOptions.includes(selectedModel)) {
            selectModelElem.value = selectedModel;
        }
    }

    // Remove hidden class from the message input
    messageElem.style.display = 'unset';

    // Focus on the message input when the page loads
    messageElem.focus();

    selectModelElem.style.display = 'block';
});

window.addEventListener('resize', () => {
    setChatContainerHeight();
});


scrollToBottom.addEventListener('click', () => {
    responsesElem.scrollTo({
        top: responsesElem.scrollHeight,
        behavior: 'smooth'
    });
});



export { };
