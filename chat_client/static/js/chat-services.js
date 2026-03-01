import { createDialog, getMessages, createMessage, updateMessage, isLoggedInOrRedirect } from './app-dialog.js';

const storageService = {
    createDialog,
    createMessage,
    updateMessage,
    getMessages,
};

const authService = {
    async ensure() { return isLoggedInOrRedirect(); },
};

const chatService = {
    async *stream(payload, signal) {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal,
        });
        if (!response.ok) {
            throw new Error(`Server returned error: ${response.status} ${response.statusText}`);
        }
        if (!response.body) {
            throw new Error('Response body is empty. Try again later.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let reasoningOpen = false;
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const rawLine of lines) {
                const line = rawLine.replace(/^data:\s*/, '').trim();
                if (!line) continue;
                if (line === '[DONE]') {
                    if (reasoningOpen) {
                        yield { reasoning: null, reasoningOpenClose: 'close' };
                        reasoningOpen = false;
                    }
                    return;
                }

                let data;
                try {
                    data = JSON.parse(line);
                } catch (_) {
                    continue;
                }

                if (typeof data.error === 'string' && data.error.trim()) {
                    throw new Error(data.error.trim());
                }
                if (data.tool_status) {
                    yield { toolStatus: data.tool_status };
                    continue;
                }
                if (data.tool_call) {
                    yield { toolCall: data.tool_call };
                    continue;
                }

                const delta = data.choices?.[0]?.delta ?? {};
                const finishReason = data.choices?.[0]?.finish_reason;

                if (delta.reasoning) {
                    if (!reasoningOpen) {
                        yield { reasoning: null, reasoningOpenClose: 'open' };
                        reasoningOpen = true;
                    }
                    yield { reasoning: delta.reasoning };
                } else if (reasoningOpen) {
                    yield { reasoning: null, reasoningOpenClose: 'close' };
                    reasoningOpen = false;
                }

                if (delta.content) yield { content: delta.content };
                if (finishReason) yield { done: true };
            }
        }

        const tail = buffer.replace(/^data:\s*/, '').trim();
        if (!tail || tail === '[DONE]') {
            if (reasoningOpen) {
                yield { reasoning: null, reasoningOpenClose: 'close' };
            }
            return;
        }

        let data;
        try {
            data = JSON.parse(tail);
        } catch (_) {
            return;
        }

        if (typeof data.error === 'string' && data.error.trim()) {
            throw new Error(data.error.trim());
        }
        if (data.tool_status) {
            yield { toolStatus: data.tool_status };
            return;
        }
        if (data.tool_call) {
            yield { toolCall: data.tool_call };
            return;
        }
        const delta = data.choices?.[0]?.delta ?? {};
        if (delta.content) yield { content: delta.content };
        if (delta.reasoning) yield { reasoning: delta.reasoning };
    },
};

export { storageService, authService, chatService };
