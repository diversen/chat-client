import { attachImageIcon, attachFileIcon, sendIcon, abortIcon } from '/static/js/app-icons.js';

function mountStaticIcons(elements) {
    elements.attachImageButtonElem.innerHTML = attachImageIcon;
    elements.attachFileButtonElem.innerHTML = attachFileIcon;
    elements.sendButtonElem.innerHTML = sendIcon;
    elements.abortButtonElem.innerHTML = abortIcon;
}

export { mountStaticIcons };
