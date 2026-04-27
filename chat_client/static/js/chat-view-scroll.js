const ANCHOR_SPACER_CLASS = 'responses-anchor-spacer';
const MIN_ANCHOR_SPACER_HEIGHT_PX = 20;
const EXTRA_STREAMING_SLACK_PX = 100;
const MESSAGE_INPUT_MIN_HEIGHT_PX = 60;
const MESSAGE_INPUT_MAX_VIEWPORT_HEIGHT_RATIO = 0.25;

function resizeMessageInput(messageElem) {
    if (!messageElem) return;

    const maxHeightPx = Math.max(
        MESSAGE_INPUT_MIN_HEIGHT_PX,
        Math.floor(window.innerHeight * MESSAGE_INPUT_MAX_VIEWPORT_HEIGHT_RATIO),
    );

    messageElem.style.height = 'auto';
    messageElem.style.height = `${Math.min(messageElem.scrollHeight, maxHeightPx)}px`;
    messageElem.style.overflowY = messageElem.scrollHeight > maxHeightPx ? 'auto' : 'hidden';
}

function resetMessageInputHeight(messageElem) {
    if (!messageElem) return;
    messageElem.style.height = `${MESSAGE_INPUT_MIN_HEIGHT_PX}px`;
    messageElem.style.overflowY = 'hidden';
}

function getOrCreateAnchorSpacer(responsesElem) {
    let spacer = responsesElem.querySelector(`.${ANCHOR_SPACER_CLASS}`);
    if (!spacer) {
        spacer = document.createElement('div');
        spacer.className = ANCHOR_SPACER_CLASS;
        spacer.setAttribute('aria-hidden', 'true');
        responsesElem.appendChild(spacer);
    }
    return spacer;
}

function appendBeforeAnchorSpacer(responsesElem, element) {
    const spacer = getOrCreateAnchorSpacer(responsesElem);
    responsesElem.insertBefore(element, spacer);
}

function getAnchorSpacerHeight(responsesElem) {
    const spacer = getOrCreateAnchorSpacer(responsesElem);
    const inlineHeight = parseFloat(spacer.style.height);
    if (Number.isFinite(inlineHeight)) {
        return Math.max(0, inlineHeight);
    }
    const computedHeight = parseFloat(window.getComputedStyle(spacer).height);
    return Number.isFinite(computedHeight) ? Math.max(0, computedHeight) : 0;
}

function setAnchorSpacerHeight(responsesElem, heightPx, animate = false) {
    const spacer = getOrCreateAnchorSpacer(responsesElem);
    spacer.style.transition = animate ? 'height 180ms ease-out' : 'none';
    spacer.style.height = `${Math.max(MIN_ANCHOR_SPACER_HEIGHT_PX, Math.ceil(heightPx))}px`;
}

function ensureScrollRoomForMessage(responsesElem, container, navOffset) {
    const currentSpacerHeight = getAnchorSpacerHeight(responsesElem);
    const targetTop = container.getBoundingClientRect().top + window.scrollY - navOffset;
    const targetScrollY = Math.max(0, targetTop);
    const doc = document.documentElement;
    // Compute max scroll without the existing spacer so we do not collapse
    // spacer room that is still required for top alignment.
    const baseScrollHeight = Math.max(0, doc.scrollHeight - currentSpacerHeight);
    // Keep this unclamped: when content is shorter than viewport, the negative
    // delta tells us exactly how much spacer is needed to make top alignment possible.
    const baseScrollDelta = baseScrollHeight - window.innerHeight;
    const requiredSpacerHeight = Math.max(0, targetScrollY - baseScrollDelta);
    setAnchorSpacerHeight(responsesElem, requiredSpacerHeight + EXTRA_STREAMING_SLACK_PX, false);
    return targetScrollY;
}

function getBaseScrollHeight(responsesElem) {
    const doc = document.documentElement;
    return Math.max(0, doc.scrollHeight - getAnchorSpacerHeight(responsesElem));
}

function consumeAnchorSpacerBy(responsesElem, usedHeightPx, animate = false) {
    if (!Number.isFinite(usedHeightPx) || usedHeightPx <= 0) return;
    const current = getAnchorSpacerHeight(responsesElem);
    if (current <= 0) return;
    setAnchorSpacerHeight(responsesElem, Math.max(MIN_ANCHOR_SPACER_HEIGHT_PX, current - usedHeightPx), animate);
}

export {
    appendBeforeAnchorSpacer,
    consumeAnchorSpacerBy,
    ensureScrollRoomForMessage,
    getBaseScrollHeight,
    resetMessageInputHeight,
    resizeMessageInput,
};
