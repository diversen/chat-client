function getFlashContainer() {
    const container = document.querySelector('.flash-messages');
    if (!container) {
        throw new Error('Missing required flash container: .flash-messages');
    }
    return container;
}

function createFlashElement(message, type, uniqueClassName = '') {
    const flashElem = document.createElement('div');
    flashElem.classList.add('flash', `flash-${type}`);
    if (uniqueClassName) {
        flashElem.classList.add(uniqueClassName);
    }
    flashElem.textContent = String(message || '');
    return flashElem;
}

function removeStaticFlashMessages() {
    const elems = document.querySelectorAll('.flash-static');
    elems.forEach((elem) => {
        elem.remove();
    });
}

function scheduleElementRemoval(element, delaySeconds) {
    if (!element || !delaySeconds) {
        return;
    }

    window.setTimeout(() => {
        element.remove();
    }, delaySeconds * 1000);
}

class Flash {
    static storageKey = 'flash_message';

    static singleMessage = true;

    static removeAfterSecs = null;

    static setMessage(message, type = 'notice') {
        const messageElem = getFlashContainer();
        messageElem.focus();

        if (this.singleMessage) {
            messageElem.innerHTML = '';
        }

        const uniqueClassName = `flash-${Math.random().toString(36).slice(2)}`;
        const flashElem = createFlashElement(message, type, uniqueClassName);
        messageElem.prepend(flashElem);

        if (this.removeAfterSecs) {
            scheduleElementRemoval(flashElem, this.removeAfterSecs);
        }
    }

    static setMessageFromError(error, fallbackMessage = 'An error occurred. Try again later.', type = 'error') {
        if (error?.redirecting === true) {
            return;
        }

        const message = (typeof error?.message === 'string' && error.message.trim())
            ? error.message.trim()
            : fallbackMessage;
        this.setMessage(message, type);
    }

    static storeMessageForNextPage(message, type = 'notice') {
        if (typeof window === 'undefined' || !window.sessionStorage) {
            return;
        }

        window.sessionStorage.setItem(this.storageKey, JSON.stringify({ message, type }));
    }

    static showStoredMessage() {
        if (typeof window === 'undefined' || !window.sessionStorage) {
            return;
        }

        const rawValue = window.sessionStorage.getItem(this.storageKey);
        if (!rawValue) {
            return;
        }

        window.sessionStorage.removeItem(this.storageKey);

        try {
            const stored = JSON.parse(rawValue);
            const message = typeof stored?.message === 'string' ? stored.message.trim() : '';
            const type = typeof stored?.type === 'string' ? stored.type : 'notice';
            if (message) {
                this.setMessage(message, type);
            }
        } catch (_) {
            // Ignore malformed client-side flash payloads.
        }
    }

    static clearMessages() {
        if (!this.removeAfterSecs) {
            return;
        }

        window.setTimeout(() => {
            removeStaticFlashMessages();
        }, this.removeAfterSecs * 1000);
    }
}

document.addEventListener('click', (event) => {
    const flashElem = event.target.closest('.flash');
    if (flashElem) {
        flashElem.remove();
    }
});

export { Flash };
