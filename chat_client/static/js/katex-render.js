import { mdNoHTML } from './markdown.js';
import { modifyStreamedText } from './utils.js';

const KATEX_DELIMITERS = [
    { left: "$$", right: "$$", display: true },
    { left: "$", right: "$", display: false },
    { left: "\\(", right: "\\)", display: false },
    { left: "\\begin{equation}", right: "\\end{equation}", display: true },
    { left: "\\begin{align}", right: "\\end{align}", display: true },
    { left: "\\begin{alignat}", right: "\\end{alignat}", display: true },
    { left: "\\begin{gather}", right: "\\end{gather}", display: true },
    { left: "\\begin{CD}", right: "\\end{CD}", display: true },
    { left: "\\[", right: "\\]", display: true },
];

const MARKDOWN_PROTECTED_KATEX_DELIMITERS = KATEX_DELIMITERS.filter((delimiter) => delimiter.left !== '$');
const KATEX_ERROR_IGNORED_TAGS = ['SCRIPT', 'NOSCRIPT', 'STYLE', 'TEXTAREA', 'PRE', 'CODE', 'OPTION'];

function createKatexErrorNode(rawContent, title) {
    const errorNode = document.createElement('span');
    errorNode.className = 'katex-error';
    errorNode.textContent = rawContent;
    if (title) {
        errorNode.title = title;
    }
    return errorNode;
}

function normalizeKatexContent(text) {
    return String(text || '').replace(/\\\\/g, '\\cr');
}

function extractFailedKatexExpression(message) {
    const match = String(message || '').match(/Failed to parse `([^`]*)`/);
    return match ? match[1] : '';
}

function getKatexErrorCandidates(expression) {
    const normalizedExpression = normalizeKatexContent(expression);
    const candidates = KATEX_DELIMITERS.map((delimiter) => ({
        raw: `${delimiter.left}${expression}${delimiter.right}`,
        normalized: `${delimiter.left}${normalizedExpression}${delimiter.right}`,
    }));

    candidates.push({
        raw: expression,
        normalized: normalizedExpression,
    });
    return candidates;
}

function createKatexPlaceholder(index) {
    return `@@KATEX_RAW_${index}@@`;
}

function splitMarkdownProtectedKatex(text) {
    const segments = [];
    let cursor = 0;

    while (cursor < text.length) {
        let bestMatch = null;
        for (const delimiter of MARKDOWN_PROTECTED_KATEX_DELIMITERS) {
            const index = text.indexOf(delimiter.left, cursor);
            if (index === -1) continue;
            if (!bestMatch || index < bestMatch.index) {
                bestMatch = { index, delimiter };
            }
        }

        if (!bestMatch) {
            segments.push({ type: 'text', content: text.slice(cursor) });
            break;
        }

        const { index, delimiter } = bestMatch;
        if (index > cursor) {
            segments.push({ type: 'text', content: text.slice(cursor, index) });
        }

        const mathStart = index + delimiter.left.length;
        const mathEnd = text.indexOf(delimiter.right, mathStart);
        if (mathEnd === -1) {
            segments.push({ type: 'text', content: text.slice(index) });
            break;
        }

        segments.push({
            type: 'math',
            rawContent: text.slice(index, mathEnd + delimiter.right.length),
        });
        cursor = mathEnd + delimiter.right.length;
    }

    return segments;
}

function replaceKatexPlaceholders(rootNode, placeholderValues) {
    const walker = document.createTreeWalker(rootNode, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    let currentNode = walker.nextNode();
    while (currentNode) {
        textNodes.push(currentNode);
        currentNode = walker.nextNode();
    }

    for (const textNode of textNodes) {
        const text = textNode.textContent || '';
        const matches = Array.from(text.matchAll(/@@KATEX_RAW_(\d+)@@/g));
        if (!matches.length) continue;

        const fragment = document.createDocumentFragment();
        let cursor = 0;
        for (const match of matches) {
            const index = Number(match[1]);
            const placeholder = match[0];
            const start = match.index ?? 0;

            if (start > cursor) {
                fragment.appendChild(document.createTextNode(text.slice(cursor, start)));
            }

            const replacementText = placeholderValues[index];
            if (replacementText) {
                fragment.appendChild(document.createTextNode(replacementText));
            } else {
                fragment.appendChild(document.createTextNode(placeholder));
            }
            cursor = start + placeholder.length;
        }

        if (cursor < text.length) {
            fragment.appendChild(document.createTextNode(text.slice(cursor)));
        }
        textNode.replaceWith(fragment);
    }
}

function replaceFirstKatexError(rootNode, failure) {
    const walker = document.createTreeWalker(rootNode, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
            const parentElement = node.parentElement;
            if (!parentElement) return NodeFilter.FILTER_REJECT;
            if (!node.textContent) return NodeFilter.FILTER_REJECT;

            const tagName = parentElement.tagName;
            if (KATEX_ERROR_IGNORED_TAGS.includes(tagName)) {
                return NodeFilter.FILTER_REJECT;
            }
            if (parentElement.closest('.katex, .katex-error')) {
                return NodeFilter.FILTER_REJECT;
            }
            return NodeFilter.FILTER_ACCEPT;
        },
    });

    const candidates = getKatexErrorCandidates(failure.expression);
    let currentNode = walker.nextNode();
    while (currentNode) {
        const text = currentNode.textContent || '';
        for (const candidate of candidates) {
            const matchedText = [candidate.raw, candidate.normalized].find((value) => value && text.includes(value));
            if (!matchedText) continue;

            const start = text.indexOf(matchedText);
            const fragment = document.createDocumentFragment();
            if (start > 0) {
                fragment.appendChild(document.createTextNode(text.slice(0, start)));
            }
            fragment.appendChild(createKatexErrorNode(matchedText, failure.message));
            const end = start + matchedText.length;
            if (end < text.length) {
                fragment.appendChild(document.createTextNode(text.slice(end)));
            }
            currentNode.replaceWith(fragment);
            return true;
        }
        currentNode = walker.nextNode();
    }
    return false;
}

function highlightKatexFailures(rootNode, failures) {
    failures.forEach((failure) => {
        replaceFirstKatexError(rootNode, failure);
    });
}

function renderMarkdownWithKatex(target, markdownText) {
    const segments = splitMarkdownProtectedKatex(markdownText);
    const placeholderValues = [];
    const protectedMarkdown = segments.map((segment) => {
        if (segment.type === 'text') return modifyStreamedText(segment.content);
        const placeholderIndex = placeholderValues.push(segment.rawContent) - 1;
        return createKatexPlaceholder(placeholderIndex);
    }).join('');

    const container = document.createElement('div');
    container.innerHTML = mdNoHTML.render(protectedMarkdown);
    replaceKatexPlaceholders(container, placeholderValues);
    while (container.firstChild) {
        target.appendChild(container.firstChild);
    }
}

function renderKatex(contentElem, useKatex) {
    if (!useKatex) return;

    const failures = [];
    renderMathInElement(contentElem, {
        delimiters: KATEX_DELIMITERS,
        throwOnError: true,
        strict: 'warn',
        preProcess: normalizeKatexContent,
        errorCallback(message, err) {
            console.warn(`KaTeX auto-render: ${message}`, err);
            const expression = extractFailedKatexExpression(message);
            if (!expression) return;
            failures.push({ expression, message });
        },
    });

    highlightKatexFailures(contentElem, failures);
}

export {
    KATEX_DELIMITERS,
    renderKatex,
    renderMarkdownWithKatex,
};
