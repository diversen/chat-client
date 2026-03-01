import { copyIcon, checkIcon } from './app-icons.js';

async function addCopyButtons(contentElem, _config) {

    const codeBlocks = contentElem.querySelectorAll('pre code');

    codeBlocks.forEach(code => {
        if (code.querySelector('.copy-button')) {
            return;
        }
        const codeText = code.textContent;
        code.classList.add('copyable-code');

        /**
         * Copy-paste code button
         */
        const button = document.createElement("button");
        button.classList.add('copy-button');
        button.type = 'button';
        button.title = 'Copy code';
        button.setAttribute('aria-label', 'Copy code');
        button.innerHTML = copyIcon;
        button.onclick = function () {
            navigator.clipboard.writeText(codeText).then(() => {
                button.innerHTML = checkIcon;

                setTimeout(() => {
                    button.innerHTML = copyIcon;
                }, 2000);

            }, err => {
                console.log('Failed to copy: ', err);
            });
        };
        code.appendChild(button);
    });
}

export { addCopyButtons };
