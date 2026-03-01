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
        captchaElem.src = `/captcha?${Math.random()}`;
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

export {
    getTrimmedValueById,
    validateRequiredFields,
    initCaptcha,
    runWithSpinner,
};
