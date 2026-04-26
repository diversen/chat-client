function getModelOptions(selectModelElem) {
    return Array.from(selectModelElem?.options || []).map((option) => String(option.value || '').trim());
}

function getSelectOptions(selectElem) {
    return Array.from(selectElem?.options || []).map((option) => String(option.value || '').trim());
}

function createModelSelection({ selectModelElem, selectedModelNameElem }) {
    let isBound = false;
    const subscribers = new Set();

    const renderSelectedModel = (modelName) => {
        const safeModelName = String(modelName || '').trim();
        if (!selectedModelNameElem) return;
        selectedModelNameElem.textContent = safeModelName;
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

    const restoreStoredModel = () => {
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
            forceNotify: true,
        });
    };

    const render = () => {
        renderSelectedModel(getSelectedModel());
    };

    const bind = () => {
        if (!selectModelElem || isBound) return;
        isBound = true;
        selectModelElem.addEventListener('change', handleSelectChange);
    };

    const subscribe = (callback) => {
        subscribers.add(callback);
        return () => {
            subscribers.delete(callback);
        };
    };

    return {
        bind,
        render,
        restoreStoredModel,
        subscribe,
        getSelectedModel,
        setSelectedModel,
        renderSelectedModel,
    };
}

function createStoredSelection({ selectElem, storageKey, defaultValue = '' }) {
    let isBound = false;
    const subscribers = new Set();

    const getSelectedValue = () => String(selectElem?.value || '').trim();

    const notifySubscribers = (value, details) => {
        subscribers.forEach((callback) => {
            callback(value, details);
        });
    };

    const setSelectedValue = (value, options = {}) => {
        const resolvedValue = String(value || '').trim();
        const validOptions = getSelectOptions(selectElem);
        if (!resolvedValue || !validOptions.includes(resolvedValue)) {
            return false;
        }

        const previousValue = getSelectedValue();
        selectElem.value = resolvedValue;

        if (options.persist !== false) {
            localStorage.setItem(storageKey, resolvedValue);
        }

        if (resolvedValue !== previousValue || options.forceNotify) {
            notifySubscribers(resolvedValue, {
                previousValue,
                source: options.source || 'programmatic',
            });
        }

        return true;
    };

    const restoreStoredValue = () => {
        const storedValue = localStorage.getItem(storageKey);
        if (!storedValue) {
            if (defaultValue) {
                setSelectedValue(defaultValue, {
                    source: 'default',
                    persist: false,
                });
            }
            return;
        }
        setSelectedValue(storedValue, {
            source: 'storage',
            persist: false,
        });
    };

    const bind = () => {
        if (!selectElem || isBound) return;
        isBound = true;
        selectElem.addEventListener('change', () => {
            setSelectedValue(selectElem.value, {
                source: 'select',
                persist: true,
                forceNotify: true,
            });
        });
    };

    const subscribe = (callback) => {
        subscribers.add(callback);
        return () => {
            subscribers.delete(callback);
        };
    };

    return {
        bind,
        subscribe,
        restoreStoredValue,
        getSelectedValue,
        setSelectedValue,
    };
}

export { createModelSelection, createStoredSelection };
