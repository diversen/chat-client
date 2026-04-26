class Requests {
    static REQUEST_TIMEOUT = 10;

    /**
     * Normalize an unknown error into a user-displayable message.
     */
    static getErrorMessage(error, fallbackMessage = 'An error occurred. Try again later.') {
        const message = error?.message;
        if (typeof message === 'string' && message.trim()) {
            return message;
        }
        return fallbackMessage;
    }

    /**
     * Helper function to fetch with timeout
     */
    static async _fetchWithTimeout(url, options = {}) {
        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => controller.abort(), Requests.REQUEST_TIMEOUT * 1000);
        const requestOptions = {
            ...options,
            signal: controller.signal,
        };

        try {
            const response = await fetch(url, requestOptions);
            clearTimeout(timeoutId);
            const responseText = await response.text();
            let responseJson = null;
            if (responseText) {
                try {
                    responseJson = JSON.parse(responseText);
                } catch {
                    responseJson = null;
                }
            }

            if (!response.ok) {
                const message =
                    responseJson?.message ||
                    `${requestOptions.method} request failed: ${response.status} ${response.statusText}`;
                const error = new Error(message);
                error.status = response.status;
                if (responseJson?.redirect) {
                    error.redirect = responseJson.redirect;
                    if (response.status === 401 && typeof window !== 'undefined') {
                        window.location.href = responseJson.redirect;
                        error.redirecting = true;
                    }
                }
                throw error;
            }

            if (!responseText) {
                return {};
            }
            if (responseJson !== null) {
                return responseJson;
            }

            throw new Error('Server returned an invalid JSON response.');
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(`${requestOptions.method} request aborted due to timeout`);
            }
            throw error;
        }
    }

    /**
     * Post FormData async. Accepts JSON as response.
     */
    static async asyncPost(url, formData, method = 'POST') {
        return Requests._fetchWithTimeout(url, {
            method,
            headers: {
                'Accept': 'application/json',
            },
            body: formData,
        });
    }

    /**
     * POST JSON async. Send a JSON object or a JSON string.
     */
    static async asyncPostJson(url, jsonData = {}, method = 'POST') {
        return Requests._fetchWithTimeout(url, {
            method,
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            body: typeof jsonData === 'string' ? jsonData : JSON.stringify(jsonData),
        });
    }

    /**
     * Get JSON async.
     */
    static async asyncGetJson(url, method = 'GET', options = {}) {
        return Requests._fetchWithTimeout(url, {
            ...options,
            method,
            headers: {
                'Accept': 'application/json',
                ...(options.headers || {}),
            },
        });
    }
}

export { Requests };
