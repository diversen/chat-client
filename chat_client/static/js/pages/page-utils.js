function getTrimmedValueById(id) {
    return String(document.getElementById(id)?.value || '').trim();
}

function validateRequiredFields(fields, onError) {
    for (const field of fields) {
        const value = String(field?.value || '').trim();
        if (value) continue;
        if (typeof onError === 'function') {
            onError(field?.message || 'Please fill out this field.');
        }
        return false;
    }
    return true;
}

function initCaptcha(captchaElem, captchaContainerElem) {
    if (!captchaElem || !captchaContainerElem) {
        return false;
    }

    const refreshCaptcha = () => {
        captchaElem.src = `/user/captcha?${Math.random()}`;
    };

    captchaElem.addEventListener('click', refreshCaptcha);
    refreshCaptcha();
    captchaContainerElem.classList.remove('hidden');
    return true;
}

async function runWithSpinner(task) {
    const spinner = document.querySelector('.loading-spinner');
    spinner.classList.remove('hidden');
    try {
        return await task();
    } finally {
        spinner.classList.add('hidden');
    }
}

function initAsyncButtonAction(buttonId, onClick) {
    const button = document.getElementById(buttonId);
    if (!button) {
        return false;
    }

    button.addEventListener('click', async (event) => {
        event.preventDefault();
        await runWithSpinner(async () => {
            await onClick(event);
        });
    });

    return true;
}

function buildFormData(formId) {
    const form = document.getElementById(formId);
    if (!form) {
        throw new Error(`Form not found: ${formId}`);
    }
    return new FormData(form);
}

function initFormSubmissionPage({
    buttonId,
    request,
    onSuccess,
    onError,
}) {
    return initAsyncButtonAction(buttonId, async () => {
        try {
            const response = await request();
            if (typeof onSuccess === 'function') {
                onSuccess(response);
            }
        } catch (error) {
            console.error(error);
            if (typeof onError === 'function') {
                onError(error);
            }
        }
    });
}

function initPromptFormPage({
    buttonId,
    titleId = 'title',
    promptId = 'custom-prompt',
    promptRecordId = null,
    getSubmitUrl,
    getSuccessRedirect = () => '/prompts',
    getSuccessMessage = (response) => response?.message,
    onError,
    requests,
    flash,
}) {
    const submitButton = document.getElementById(buttonId);
    if (!submitButton) {
        return;
    }

    submitButton.addEventListener('click', async (event) => {
        event.preventDefault();

        const title = getTrimmedValueById(titleId);
        const prompt = getTrimmedValueById(promptId);

        const isValid = validateRequiredFields(
            [
                { value: title, message: 'Please enter a title.' },
                { value: prompt, message: 'Please enter a prompt.' },
            ],
            (message) => flash.setMessage(message, 'error'),
        );
        if (!isValid) {
            return;
        }

        const submitUrl = typeof getSubmitUrl === 'function'
            ? getSubmitUrl({ promptRecordId })
            : '';
        if (!submitUrl) {
            flash.setMessage('Prompt endpoint is missing.', 'error');
            return;
        }

        try {
            const response = await requests.asyncPostJson(submitUrl, { title, prompt });
            const successMessage = typeof getSuccessMessage === 'function'
                ? getSuccessMessage(response)
                : response?.message;
            if (successMessage) {
                flash.storeMessageForNextPage(successMessage, 'success');
            }
            window.location.href = typeof getSuccessRedirect === 'function'
                ? getSuccessRedirect(response)
                : '/prompts';
        } catch (error) {
            console.error(error);
            if (typeof onError === 'function') {
                onError(error);
                return;
            }
            flash.setMessageFromError(error);
        }
    });
}

export {
    getTrimmedValueById,
    validateRequiredFields,
    initCaptcha,
    runWithSpinner,
    initAsyncButtonAction,
    buildFormData,
    initFormSubmissionPage,
    initPromptFormPage,
};
