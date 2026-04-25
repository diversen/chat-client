import { selectModelIcon } from '/static/js/app-icons.js';
import { createModelSelection } from '/static/js/model-selection.js';

function initModelPicker(elements) {
    elements.modelPickerDisplayElem.innerHTML = selectModelIcon;
    return createModelSelection(elements);
}

export { initModelPicker };
