import { responsesElem, messageElem, sendButtonElem, newButtonElem, abortButtonElem, selectModelElem } from '/static/js/app-elements.js';

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

/** 
 * Add event listner to the textarea. isScrolling indicates if text is being generated
 * and is scrolling to the bottom. The user can scroll up to stop the auto-scrolling.
 */
function handleScrollEvent(event) {
    if (event.deltaY < 0) {
        console.log('Wheel up to go up in messages');
        setIsScrolling(false);
    } else if (event.deltaY > 0) {
        if (responsesElem.scrollTop + responsesElem.clientHeight >= responsesElem.scrollHeight - SCROLL_THRESHOLD) {
            setIsScrolling(true);
        }
    }
}

responsesElem.addEventListener('wheel', handleScrollEvent, { passive: true });

/**
 * Add event listener to the touch events. isScrolling indicates if text is being generated
 */
let startY = 0;

function handleTouchStart(event) {
    startY = event.touches[0].clientY;
}

function handleTouchMove(event) {
    let deltaY = event.touches[0].clientY - startY;

    if (deltaY > -TOUCH_THRESHOLD) {
        console.log('Swiping down to go up in messages');
        setIsScrolling(false);
    } else if (deltaY < TOUCH_THRESHOLD) {
        if (responsesElem.scrollTop + responsesElem.clientHeight >= responsesElem.scrollHeight - SCROLL_THRESHOLD) {
            console.log('Swiping up to go down in messages and auto-scroll again');
            setIsScrolling(true);
        }
    }
}

document.addEventListener('touchstart', handleTouchStart, { passive: true });
document.addEventListener('touchmove', handleTouchMove, { passive: true });


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

/**
 * On page load, check if a model is saved in local storage and set it as the selected model
 */
window.addEventListener('load', () => {
    let selectedModel = localStorage.getItem('selectedModel');
    if (selectedModel) {
        console.log('Selected model:', selectedModel);

        // Check if the selected model is in the list of available models
        const modelOptions = Array.from(selectModelElem.options).map(option => option.value);
        if (modelOptions.includes(selectedModel)) {
            selectModelElem.value = selectedModel;
        }
    }
    selectModelElem.style.display = 'block';
});

export { getIsScrolling, setIsScrolling };
