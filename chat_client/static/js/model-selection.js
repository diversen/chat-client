function getModelOptions(selectModelElem) {
    return Array.from(selectModelElem?.options || []).map((option) => String(option.value || '').trim());
}

function createModelSelection({ selectModelElem, selectedModelNameElem, selectedModelCompactNameElem }) {
    let initialized = false;
    const subscribers = new Set();

    const renderSelectedModel = (modelName) => {
        const safeModelName = String(modelName || '').trim();
        if (selectedModelNameElem) {
            selectedModelNameElem.textContent = safeModelName;
        }
        if (selectedModelCompactNameElem) {
            selectedModelCompactNameElem.textContent = safeModelName;
        }
    };

    const notifySubscribers = (modelName, details) => {
        subscribers.forEach((callback) => {
            callback(modelName, details);
        });
    };

    const getSelectedModel = () => String(selectModelElem?.value || '').trim();

    const setSelectedModel = (modelName, options = {}) => {
        const resolvedModel = String(modelName || '').trim();
        if (!resolvedModel) return false;

        const modelOptions = getModelOptions(selectModelElem);
        if (!modelOptions.includes(resolvedModel)) {
            return false;
        }

        const previousModel = getSelectedModel();
        selectModelElem.value = resolvedModel;
        renderSelectedModel(resolvedModel);

        if (options.persist !== false) {
            localStorage.setItem('selectedModel', resolvedModel);
        }

        if (resolvedModel !== previousModel || options.forceNotify) {
            notifySubscribers(resolvedModel, {
                previousModel,
                source: options.source || 'programmatic',
            });
        }

        return true;
    };

    const applyStoredModel = () => {
        const storedModel = localStorage.getItem('selectedModel');
        if (!storedModel) return;
        setSelectedModel(storedModel, {
            source: 'storage',
            persist: false,
        });
    };

    const handleSelectChange = () => {
        setSelectedModel(selectModelElem.value, {
            source: 'select',
            persist: true,
        });
    };

    const initialize = () => {
        if (!selectModelElem || initialized) {
            renderSelectedModel(getSelectedModel());
            return;
        }

        initialized = true;
        applyStoredModel();
        renderSelectedModel(getSelectedModel());
        selectModelElem.addEventListener('change', handleSelectChange);
    };

    const subscribe = (callback) => {
        subscribers.add(callback);
        return () => {
            subscribers.delete(callback);
        };
    };

    return {
        initialize,
        subscribe,
        getSelectedModel,
        setSelectedModel,
        renderSelectedModel,
    };
}

export { createModelSelection };
