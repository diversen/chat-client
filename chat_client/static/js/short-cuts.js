function initShortcuts() {
    document.addEventListener('keydown', (event) => {
        if (event.ctrlKey && event.shiftKey && event.key === 'O') {
            event.preventDefault();
            window.location.href = '/';
        }
    });
}

export { initShortcuts };
