import {
    classifyFinalizedAssistantSegment,
    createAssistantSegmentTurnEvent,
    createToolCallTurnEvent,
} from '/static/js/chat-turn-events.js';

function createAssistantStreamSession({ view }) {
    const streamedTurnEvents = [];
    let turnId = '';
    let turnUi = null;

    const appendAssistantTurnEvent = (event) => {
        streamedTurnEvents.push(event);
    };

    const ensureAssistantContainer = async (kind = 'Thinking', options = {}) => {
        if (!turnUi) {
            turnUi = view.createAssistantTurn();
        }
        let segment = turnUi.ensureAssistantSegment(kind, options);
        if (!segment) {
            await finalizeAssistantContainer();
            segment = turnUi.ensureAssistantSegment(kind, options);
        }
        return segment;
    };

    const ensureLoadingAnswerContainer = async () => {
        const segment = await ensureAssistantContainer('Answer', {
            showLoader: true,
            transient: true,
            previewStep: true,
            displayKind: 'Waiting for model',
        });
        segment.setLoading(true);
        segment.clearStatus();
        return segment;
    };

    const activateToolStatusSegment = async (toolName = 'tool') => {
        const activeUi = await ensureAssistantContainer('Tool', {
            showLoader: true,
            transient: true,
            previewStep: true,
        });
        activeUi.setLoading(true);
        activeUi.setStatus(`Calling tool: ${String(toolName || 'tool')}...`);
        return activeUi;
    };

    const activateThinkingSegment = async () => {
        const activeUi = await ensureAssistantContainer('Thinking');
        activeUi.setLoading(true);
        activeUi.clearStatus();
        return activeUi;
    };

    const activateAnswerSegment = async () => {
        const activeUi = await ensureAssistantContainer('Answer');
        activeUi.promote({ kind: 'Answer', showStep: true });
        activeUi.setLoading(true);
        activeUi.clearStatus();
        return activeUi;
    };

    const finalizeAssistantContainer = async () => {
        if (!turnUi) return;
        const finalized = await turnUi.finalizeAssistantSegment();
        if (!finalized) return;
        const classified = classifyFinalizedAssistantSegment(finalized);

        if (classified.action === 'discard') {
            finalized.container.remove();
            return;
        }

        if (classified.action === 'answer') {
            appendAssistantTurnEvent(createAssistantSegmentTurnEvent({ contentText: classified.text }));
            return;
        }

        if (classified.action === 'thinking') {
            appendAssistantTurnEvent(createAssistantSegmentTurnEvent({ reasoningText: classified.text }));
            return;
        }

        finalized.container.remove();
    };

    return {
        async start() {
            await ensureLoadingAnswerContainer();
        },
        async processChunk(chunk) {
            if (chunk.turnId) {
                turnId = String(chunk.turnId || '').trim();
                return;
            }
            if (chunk.toolStatus) {
                const currentSegment = turnUi ? turnUi.getActiveAssistantSegment() : null;
                if (currentSegment && currentSegment.segmentKind !== 'tool') {
                    await finalizeAssistantContainer();
                }
                await activateToolStatusSegment(chunk.toolStatus.tool_name);
                return;
            }
            if (chunk.toolCall) {
                await finalizeAssistantContainer();
                if (!turnUi) {
                    turnUi = view.createAssistantTurn();
                }
                turnUi.appendToolCall(chunk.toolCall);
                appendAssistantTurnEvent(createToolCallTurnEvent(chunk.toolCall));
                return;
            }

            if (chunk.reasoningOpenClose || chunk.reasoning) {
                const activeUi = await activateThinkingSegment();
                if (chunk.reasoning) {
                    void activeUi.appendText(chunk.reasoning);
                }
            }

            if (chunk.content) {
                const activeUi = await activateAnswerSegment();
                void activeUi.appendText(chunk.content, Boolean(chunk.done));
            }
        },
        clearActiveSegmentLoading() {
            if (!turnUi) return;
            const activeUi = turnUi.getActiveAssistantSegment();
            if (activeUi) {
                activeUi.setLoading(false);
            }
        },
        async finalize() {
            await finalizeAssistantContainer();

            if (turnUi) {
                const liveTurnContainer = turnUi.container;
                if (streamedTurnEvents.length > 0) {
                    const segmentOpenStates = Array.from(
                        liveTurnContainer.querySelectorAll('.assistant-segment-header.assistant-segment-toggle'),
                    ).map((toggle) => String(toggle.getAttribute('aria-expanded') || '').toLowerCase() === 'true');
                    await view.renderStaticAssistantTurn(streamedTurnEvents, liveTurnContainer, { segmentOpenStates });
                    liveTurnContainer.remove();
                } else {
                    turnUi.removeIfEmpty();
                }
                turnUi = null;
            }

            return {
                turnId,
                events: [...streamedTurnEvents],
            };
        },
    };
}

export { createAssistantStreamSession };
