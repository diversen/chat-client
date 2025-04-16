/**
 * Simple Requests module for making async requests: 
 * Posting a FormData object
 * Posting a JSON object
 * Getting JSON from a URL
 */

class Requests {
    
    static REQUEST_TIMEOUT = 10;

    /**
     * Helper function to fetch with timeout
     */
    static async _fetchWithTimeout(url, options) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), Requests.REQUEST_TIMEOUT * 1000);
        options.signal = controller.signal;

        try {
            const response = await fetch(url, options);
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`${options.method} request failed: ${response.status} ${response.statusText}`);
            }
            return response.json();
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(`${options.method} request aborted due to timeout`);
            }
            throw error;
        }
    }

    /**
     * Post FormData async. Accepts JSON as response.
     */
    static async asyncPost(url, formData, method = 'POST') {
        return Requests._fetchWithTimeout(url, {
            method: method,
            headers: {
                'Accept': 'application/json',
            },
            body: formData
        });
    }

    /**
     * POST JSON async. Send a JSON object or a JSON string.
     */
    static async asyncPostJson(url, jsonData = {}, method = 'POST') {
        if (typeof jsonData !== 'string') {
            jsonData = JSON.stringify(jsonData);
        }

        return Requests._fetchWithTimeout(url, {
            method: method,
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: jsonData
        });
    }

    /**
     * Get JSON async.
     */
    static async asyncGetJson(url, method = 'GET') {
        return Requests._fetchWithTimeout(url, {
            method: method,
            headers: {
                'Accept': 'application/json',
            }
        });
    }
}

export { Requests };