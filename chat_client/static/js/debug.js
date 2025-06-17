
const eventsToLog = [
    'paste', 'input', 
    'keydown', 'keyup', 
    'compositionstart', 'compositionupdate', 'compositionend'
];

const logEvent = (e) => {
    const details = {
        type: e.type,
        isTrusted: e.isTrusted,
    };
    if (e.key) details.key = e.key;
    if (e.inputType) details.inputType = e.inputType;
    if (e.data) details.data = e.data;

    console.log(`EVENT >>`, details);

    // Add to #reponses id
    const logElem = document.createElement('div');
    logElem.classList.add('event-log');
    logElem.innerHTML = `<strong>${e.type}</strong>: ${JSON.stringify(details)}`;
    responsesElem.appendChild(logElem);
};

eventsToLog.forEach(eventType => {
    messageElem.addEventListener(eventType, logEvent);
});

// Also add the original send logic without any extra checks
messageElem.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        if (e.ctrlKey) {
            // Newline logic
            const start = messageElem.selectionStart;
            const end = messageElem.selectionEnd;
            messageElem.value = messageElem.value.substring(0, start) + '\n' + messageElem.value.substring(end);
            messageElem.selectionStart = messageElem.selectionEnd = start + 1;
        } else {
            console.log('--- SENDING MESSAGE ---');
            // await sendUserMessage(); // Comment out to prevent sending while testing
        }
    }
});

console.log('--- Event Logger Attached. Ready for testing. ---');