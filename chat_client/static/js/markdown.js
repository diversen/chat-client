import { markdownItTable } from '/static/dist/markdown-it-table.js';

/**
 * This a loaded script for markdown-it
 */
const md = markdownit('commonmark');
const mdNoHTML = markdownit('commonmark', { html: false });

md.use(markdownItTable);
mdNoHTML.use(markdownItTable);

export { md, mdNoHTML };
