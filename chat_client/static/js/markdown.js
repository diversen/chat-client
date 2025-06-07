import { markdownItTable } from '/static/dist/markdown-it-table.js';

/**
 * markdown-it is loaded in the head of the HTML file.
 */
const md = markdownit('commonmark');
const mdNoHTML = markdownit('commonmark', { html: false });

md.use(markdownItTable);
mdNoHTML.use(markdownItTable);

// keep a reference to the default renderer
const defaultLinkOpen =
    md.renderer.rules.link_open ||
    function (tokens, idx, options, env, self) {
        return self.renderToken(tokens, idx, options);
    };


const mdLinkOpen = function (tokens, idx, options, env, self) {
    const token = tokens[idx];

    // target="_blank"
    if (token.attrIndex('target') < 0) {
        token.attrPush(['target', '_blank']);
    } else {
        token.attrs[token.attrIndex('target')][1] = '_blank';
    }

    // rel="noopener noreferrer" (recommended for security)
    if (token.attrIndex('rel') < 0) {
        token.attrPush(['rel', 'noopener noreferrer']);
    }

    return defaultLinkOpen(tokens, idx, options, env, self);
};

md.renderer.rules.link_open = mdLinkOpen;
mdNoHTML.renderer.rules.link_open = mdLinkOpen;


export { md, mdNoHTML };
