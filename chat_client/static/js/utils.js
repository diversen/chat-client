function escapeKatexDelimiters(textToProcess) {

    textToProcess = textToProcess.replace(/(?<!\\)\\\(/g, '\\\\(');
    textToProcess = textToProcess.replace(/(?<!\\)\\\)/g, '\\\\)');
    textToProcess = textToProcess.replace(/(?<!\\)\\\[/g, '\\\\[');
    textToProcess = textToProcess.replace(/(?<!\\)\\\]/g, '\\\\]');    
    return textToProcess;
}

/**
 * Substitute thinking tags
 */
function modifyStreamedText(textToProcess) {
    // Substitute '\\' with '\cr '
    textToProcess = textToProcess.replace(/\\\\/g, '\\cr');
    textToProcess = escapeKatexDelimiters(textToProcess);

    return textToProcess;
}

export { modifyStreamedText };
