async function addCopyButtons(contentElem, _config) {

    const codeBlocks = contentElem.querySelectorAll('pre code');

    codeBlocks.forEach(code => {

        // Wrap button in a div and insert before code block
        const codeButtonContainer = document.createElement('div');
        codeButtonContainer.classList.add('code-button-container');

        /**
         * Copy-paste code button
         */
        const button = document.createElement("button");
        button.classList.add('copy-button');
        button.textContent = "Copy code";
        button.onclick = function () {
            navigator.clipboard.writeText(code.textContent).then(() => {
                button.textContent = "Copied!";

                setTimeout(() => {
                    button.textContent = "Copy code";
                }, 2000);

            }, err => {
                console.log('Failed to copy: ', err);
            });
        };

        codeButtonContainer.appendChild(button);

        const parent = code.parentNode;
        parent.insertBefore(codeButtonContainer, code);
    });
}

export { addCopyButtons };
