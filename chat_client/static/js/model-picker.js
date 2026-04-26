import { selectModelIcon, selectReasoningIcon } from '/static/js/app-icons.js';
import { createModelSelection, createStoredSelection } from '/static/js/model-selection.js';

function initModelPicker(elements) {
    elements.modelPickerDisplayElem.innerHTML = selectModelIcon;
    return createModelSelection(elements);
}

function initReasoningSelection(elements) {
    elements.reasoningPickerDisplayElem.innerHTML = selectReasoningIcon;
    return createStoredSelection({
        selectElem: elements.selectReasoningEffortElem,
        storageKey: 'selectedReasoningEffort',
        defaultValue: 'none',
    });
}

export { initModelPicker, initReasoningSelection };
