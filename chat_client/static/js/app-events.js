import { responsesElem, messageElem, sendButtonElem, newButtonElem, abortButtonElem, selectModelElem, chatContainer, scrollToBottom } from '/static/js/app-elements.js';

const SCROLL_THRESHOLD = 200;
const TOUCH_THRESHOLD = 10;

let isScrolling = false;

function getIsScrolling() {
    if (isScrolling) {
        return true;
    }
    return false;
}

function setIsScrolling(value) {
    isScrolling = value;
}

// sendButtonElem is disabled by default
sendButtonElem.setAttribute('disabled', true);

// Add event to sendButtonElem to remove disabled when content exists in messageElem
messageElem.addEventListener('input', () => {
    if (messageElem.value.trim().length > 0) {
        sendButtonElem.removeAttribute('disabled');
    } else {
        sendButtonElem.setAttribute('disabled', true);
    }
});

// Focus on the message input when the page loads
messageElem.focus();

/**
 * On select model change save the selected model in local storage
 */
selectModelElem.addEventListener('change', () => {
    const selectedModel = selectModelElem.value;
    localStorage.setItem('selectedModel', selectedModel);
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
        console.log('Selected model:', selectedModel);

        // Check if the selected model is in the list of available models
        const modelOptions = Array.from(selectModelElem.options).map(option => option.value);
        if (modelOptions.includes(selectedModel)) {
            selectModelElem.value = selectedModel;
        }
    }
    messageElem.style.display = 'unset';
    selectModelElem.style.display = 'block';
});


window.addEventListener('resize', () => {
    setChatContainerHeight();
});

export { getIsScrolling, setIsScrolling };
