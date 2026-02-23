import { markdownItTable } from '/static/dist/markdown-it-table.js';

/**
 * markdown-it is loaded in the head of the HTML file.
 */
const mdNoHTML = markdownit('commonmark', { html: false });

mdNoHTML.use(markdownItTable);

/**
 * Add target/_blank + rel noopener noreferrer to links
 */
const defaultLinkOpen =
  mdNoHTML.renderer.rules.link_open ||
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

  // rel="noopener noreferrer"
  if (token.attrIndex('rel') < 0) {
    token.attrPush(['rel', 'noopener noreferrer']);
  } else {
    token.attrs[token.attrIndex('rel')][1] = 'noopener noreferrer';
  }

  return defaultLinkOpen(tokens, idx, options, env, self);
};

mdNoHTML.renderer.rules.link_open = mdLinkOpen;

/**
 * Wrap every <table> in a div that provides horizontal scrolling
 * so only the table area scrolls on small screens.
 *
 * Output:
 * <div class="table-scroll"><table>...</table></div>
 */
function addTableWrapper(instance) {
  const defaultTableOpen =
    instance.renderer.rules.table_open ||
    function (tokens, idx, options, env, self) {
      return self.renderToken(tokens, idx, options);
    };

  const defaultTableClose =
    instance.renderer.rules.table_close ||
    function (tokens, idx, options, env, self) {
      return self.renderToken(tokens, idx, options);
    };

  instance.renderer.rules.table_open = function (tokens, idx, options, env, self) {
    return `<div class="markdown-table">` + defaultTableOpen(tokens, idx, options, env, self);
  };

  instance.renderer.rules.table_close = function (tokens, idx, options, env, self) {
    return defaultTableClose(tokens, idx, options, env, self) + `</div>`;
  };
}

addTableWrapper(mdNoHTML);

export { mdNoHTML };
