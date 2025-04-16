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
function modifySteamedText(textToProcess) {


    textToProcess = textToProcess.replace(/<think>/g, '**Think begin**');
    textToProcess = textToProcess.replace(/<thinking>/g, '**Think begin**');
    textToProcess = textToProcess.replace(/<thought>/g, '**Think begin**');

    textToProcess = textToProcess.replace(/<\/think>/g, '**Think end**');
    textToProcess = textToProcess.replace(/<\/thinking>/g, '**Think end**');
    textToProcess = textToProcess.replace(/<\/thought>/g, '**Think end**');

    // Substitute '\\' with '\cr '
    
    textToProcess = textToProcess.replace(/\\\\/g, '\\cr');
    textToProcess = escapeKatexDelimiters(textToProcess);

    
    return textToProcess;
}

export { modifySteamedText };