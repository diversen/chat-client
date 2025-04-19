import { md } from '/static/js/markdown.js';

async function addCopyButtons(contentElem, config) {

    const codeBlocks = contentElem.querySelectorAll('pre code');

    codeBlocks.forEach(code => {

        // Wrap button in a div and insert before code block
        const codeButtonContainer = document.createElement('div');
        codeButtonContainer.classList.add('code-button-container');

        /**
         * Button for executing Python code
         */
        if (code.classList.contains('language-python') && config.tools_callback.python) {
            const executeButton = document.createElement("button");
            executeButton.classList.add('copy-button');
            executeButton.textContent = "Execute code";
            executeButton.onclick = async function () {

                // POST response and expect JSON response
                const data = await fetch('/tools/python', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: code.textContent }),
                }).then(response => response.json())

                // Remove existing output
                const existingOutput = contentElem.querySelector('.executed-code-container');
                if (existingOutput) {
                    existingOutput.remove();
                }

                // add data.text to bottom of assistantResponseElem
                const outputElem = document.createElement('div');
                outputElem.classList.add('executed-code-container');
                outputElem.textContent = data.text;

                // The output element should be attached right after the code block
                code.parentNode.insertBefore(outputElem, code.nextSibling);
                
                // assistantResponseElem.appendChild(outputElem);

                // Render output as markdown
                const outputText = outputElem.textContent;
                outputElem.innerHTML = md.render(outputText);
                outputElem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

            };
            codeButtonContainer.appendChild(executeButton);
        }

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