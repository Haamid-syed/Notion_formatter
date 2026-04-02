import mistune
import re
import emoji
from urllib.parse import urlparse


NOTION_SUPPORTED_LANGS = {
    "abap", "arduino", "bash", "basic", "c", "c#", "c++", "clojure",
    "coffeescript", "css", "dart", "diff", "docker", "elixir", "elm",
    "erlang", "f#", "flow", "fortran", "gherkin", "glsl", "go", "graphql",
    "groovy", "haskell", "html", "java", "javascript", "json", "julia",
    "kotlin", "latex", "less", "lisp", "lua", "makefile", "markdown",
    "matlab", "mermaid", "nix", "objective-c", "ocaml", "pascal", "perl",
    "php", "plain text", "powershell", "prolog", "protobuf", "python", "r",
    "reason", "ruby", "rust", "sass", "scala", "scheme", "scss", "shell",
    "sql", "swift", "toml", "typescript", "vb.net", "verilog", "vhdl",
    "visual basic", "webassembly", "xml", "yaml",
}
LANG_ALIASES = {
    "js": "javascript", "ts": "typescript", "py": "python",
    "sh": "shell", "rb": "ruby", "rs": "rust", "md": "markdown",
}


class MarkdownConverter:
    def __init__(self):
        self.markdown = mistune.create_markdown(
            renderer='ast',
            plugins=['table', 'strikethrough'],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert_fast(self, markdown_text: str) -> list[dict]:
        """Convert a Markdown string to a flat list of Notion block dicts."""
        if not markdown_text:
            return []
        markdown_text = self._preprocess_markdown(markdown_text)
        ast = self.markdown(markdown_text)
        return self._nodes_to_blocks(ast)

    # Keep `convert` as an alias for backwards compatibility
    def convert(self, markdown_text: str) -> list[dict]:
        return self.convert_fast(markdown_text)

    # ------------------------------------------------------------------
    # Pre-processing
    # ------------------------------------------------------------------

    def _preprocess_markdown(self, text: str) -> str:
        """Fix common LLM-generated Markdown quirks before parsing."""
        if not text:
            return ""
        lines = text.split('\n')
        fixed = []
        for line in lines:
            # Split "## Heading | col1 | col2 |" into heading + table line
            if line.strip().startswith('#') and line.count('|') >= 2:
                pipe_idx = line.find('|')
                heading_part = line[:pipe_idx].strip()
                table_part = line[pipe_idx:].strip()
                fixed.append(heading_part)
                fixed.append('')  # blank line required before table
                fixed.append(table_part)
            else:
                fixed.append(line)
        return '\n'.join(fixed)

    # ------------------------------------------------------------------
    # Core dispatcher
    # ------------------------------------------------------------------

    def _nodes_to_blocks(self, nodes: list) -> list[dict]:
        """Convert a list of AST nodes to a flat list of Notion blocks."""
        blocks = []
        for node in nodes:
            result = self._node_to_block(node)
            if isinstance(result, list):
                blocks.extend(result)
            elif result is not None:
                blocks.append(result)
        return blocks

    def _node_to_block(self, node: dict):
        """Map a single AST node → one Notion block, a list of blocks, or None."""
        t = node.get('type')

        if t == 'heading':
            level = min(max(node.get('attrs', {}).get('level', 1), 1), 3)
            btype = f'heading_{level}'
            return self._rich_blocks(btype, self._rich_text(node))

        if t == 'paragraph':
            return self._rich_blocks('paragraph', self._rich_text(node))

        if t == 'list':
            return self._parse_list(node)

        if t == 'list_item':
            # Fallback when a list_item appears at top level (shouldn't happen normally)
            return self._parse_list_item(node, 'bulleted_list_item')

        if t == 'block_code':
            return self._parse_code_block(node)

        if t == 'block_quote':
            return self._parse_blockquote(node)

        if t == 'table':
            return self._parse_table(node)

        if t in ('blank_line', None):
            return None

        if t == 'thematic_break':
            return {'object': 'block', 'type': 'divider', 'divider': {}}

        # Fallback: render any unknown node as a plain paragraph
        raw = node.get('raw', node.get('text', ''))
        if not raw:
            return None
        return {
            'object': 'block', 'type': 'paragraph',
            'paragraph': {'rich_text': self._split_text(raw)},
        }

    # ------------------------------------------------------------------
    # Block parsers
    # ------------------------------------------------------------------

    def _parse_list(self, node: dict) -> list[dict]:
        is_ordered = node.get('attrs', {}).get('ordered', False)
        item_type = 'numbered_list_item' if is_ordered else 'bulleted_list_item'
        blocks = []
        for child in node.get('children', []):
            if child.get('type') == 'list_item':
                b = self._parse_list_item(child, item_type)
                if b:
                    blocks.append(b)
        return blocks

    def _parse_list_item(self, node: dict, item_type: str) -> dict | None:
        children = node.get('children', [])
        if not children:
            return None

        # First child holds the inline text (block_text or paragraph)
        first = children[0]
        if first.get('type') in ('block_text', 'paragraph'):
            rich_texts = self._rich_text(first)
            rest = children[1:]
        else:
            rich_texts = []
            rest = children

        # Any remaining children (e.g. nested lists) become Notion children
        nested = self._nodes_to_blocks(rest)

        block = {
            'object': 'block',
            'type': item_type,
            item_type: {'rich_text': rich_texts},
        }
        if nested:
            block[item_type]['children'] = nested
        return block

    def _parse_code_block(self, node: dict) -> dict:
        info = (node.get('attrs', {}).get('info') or '').strip().lower()
        language = LANG_ALIASES.get(info, info)
        if language not in NOTION_SUPPORTED_LANGS:
            language = 'plain text'
        raw = node.get('raw', '')
        return {
            'object': 'block', 'type': 'code',
            'code': {
                'rich_text': self._split_text(raw),
                'language': language,
            },
        }

    def _parse_blockquote(self, node: dict):
        """
        Blockquote handling:
        - Starts with '!toggle <title>' → Notion toggle block
        - Starts with '!page <title>'   → heading_3 label
        - Otherwise                     → Notion quote block(s)

        Key insight from Mistune's AST:
        A blockquote wrapping "> !toggle Title\n> content\n> more"
        produces ONE paragraph child whose inline children are:
          [text("!toggle Title"), softbreak, text("content"), softbreak, text("more")]

        For toggles we split that first paragraph on the first softbreak:
          - everything before = title
          - everything after  = first content paragraph (may be empty)
        Subsequent children (lists, code blocks, etc.) become toggle children as-is.
        """
        children = node.get('children', [])
        if not children:
            return None

        first = children[0]
        first_text = self._get_raw_text(first)

        # -------- toggle --------
        if first_text.startswith('!toggle'):
            title, inline_content = self._split_toggle_first_paragraph(first)
            if not title:
                title = 'Toggle Details'

            toggle_children = []
            # If there was content on the same paragraph lines after the title
            if inline_content:
                body_rich = []
                for inline_node in inline_content:
                    body_rich.extend(self._rich_text_inline(inline_node))
                if body_rich:
                    toggle_children.append({
                        'object': 'block', 'type': 'paragraph',
                        'paragraph': {'rich_text': body_rich},
                    })

            # All other children of the blockquote become toggle children
            for child in children[1:]:
                result = self._node_to_block(child)
                if isinstance(result, list):
                    toggle_children.extend(result)
                elif result:
                    toggle_children.append(result)

            if not toggle_children:
                toggle_children.append({
                    'object': 'block', 'type': 'paragraph',
                    'paragraph': {'rich_text': [{'type': 'text', 'text': {'content': 'Content goes here.'}}]},
                })

            return {
                'object': 'block', 'type': 'toggle',
                'toggle': {
                    'rich_text': self._split_text(title),
                    'children': toggle_children,
                },
            }

        # -------- !page label --------
        if first_text.startswith('!page'):
            page_title = first_text.replace('!page', '', 1).strip()
            return {
                'object': 'block', 'type': 'heading_3',
                'heading_3': {'rich_text': self._split_text(f'> Page Segment: {page_title}')},
            }

        # -------- regular blockquote --------
        # Render each child: paragraphs become quote blocks; other nodes stay as-is
        results = []
        for child in children:
            ct = child.get('type')
            if ct in ('paragraph', 'block_text'):
                rts = self._rich_text(child)
                if rts:
                    results.extend(self._rich_blocks('quote', rts))
            else:
                b = self._node_to_block(child)
                if isinstance(b, list):
                    results.extend(b)
                elif b:
                    results.append(b)
        return results

    def _parse_table(self, node: dict) -> dict | None:
        """
        Mistune AST for a table:
          table
            table_head  ← cells are DIRECT children (not wrapped in table_row)
              table_cell, table_cell, ...
            table_body
              table_row
                table_cell, table_cell, ...
              table_row
                ...
        """
        children = node.get('children', [])
        rows = []
        table_width = 0
        has_header = False

        for section in children:
            stype = section.get('type')

            if stype == 'table_head':
                has_header = True
                # Cells are direct children of table_head (no table_row wrapper)
                cells = []
                for tc in section.get('children', []):
                    if tc.get('type') == 'table_cell':
                        rt = self._rich_text(tc)
                        cells.append(rt if rt else [{'type': 'text', 'text': {'content': ' '}}])
                if cells:
                    table_width = max(table_width, len(cells))
                    rows.append({
                        'object': 'block', 'type': 'table_row',
                        'table_row': {'cells': cells},
                    })

            elif stype == 'table_body':
                for tr in section.get('children', []):
                    if tr.get('type') == 'table_row':
                        cells = []
                        for tc in tr.get('children', []):
                            if tc.get('type') == 'table_cell':
                                rt = self._rich_text(tc)
                                cells.append(rt if rt else [{'type': 'text', 'text': {'content': ' '}}])
                        if cells:
                            table_width = max(table_width, len(cells))
                            rows.append({
                                'object': 'block', 'type': 'table_row',
                                'table_row': {'cells': cells},
                            })

        if table_width == 0:
            return None

        return {
            'object': 'block', 'type': 'table',
            'table': {
                'table_width': table_width,
                'has_column_header': has_header,
                'has_row_header': False,
                'children': rows,
            },
        }

    # ------------------------------------------------------------------
    # Rich text helpers
    # ------------------------------------------------------------------

    def _split_toggle_first_paragraph(self, para_node: dict) -> tuple[str, list]:
        """
        Given the first paragraph of a !toggle blockquote, split on the first
        softbreak to separate the title from any inline content that follows.

        Returns (title_str, [remaining_inline_nodes])
        """
        inline_children = para_node.get('children', [])
        title_parts = []
        rest_nodes = []
        found_break = False

        for child in inline_children:
            ct = child.get('type')
            if not found_break:
                if ct in ('softbreak', 'linebreak', 'hardbreak'):
                    found_break = True
                else:
                    raw = child.get('raw', child.get('text', ''))
                    title_parts.append(raw)
            else:
                if ct not in ('softbreak', 'linebreak', 'hardbreak'):
                    rest_nodes.append(child)

        raw_title = ''.join(title_parts).replace('!toggle', '', 1).strip()
        return raw_title, rest_nodes

    def _get_raw_text(self, node: dict) -> str:
        """Recursively extract plain text content from a node."""
        parts = []
        if 'raw' in node:
            parts.append(node['raw'])
        elif 'text' in node:
            parts.append(node['text'])
        for child in node.get('children', []):
            parts.append(self._get_raw_text(child))
        return ''.join(parts)

    def _rich_text(self, node: dict) -> list[dict]:
        """Extract a list of Notion rich_text objects from a node's inline children."""
        children = node.get('children', [])
        if not children:
            raw = node.get('raw', node.get('text', ''))
            return self._split_text(raw) if raw else []

        rich_texts = []
        state = {'underline': False}

        def add(text, anns=None):
            if not text:
                return
            merged = (anns or {}).copy()
            if state['underline']:
                merged['underline'] = True
            rich_texts.extend(self._split_text(text, merged or None))

        for child in children:
            rich_texts.extend(self._rich_text_inline(child, state, add))

        return rich_texts

    def _rich_text_inline(self, child: dict, state: dict = None, add=None) -> list[dict]:
        """Convert a single inline AST node into rich_text items."""
        if state is None:
            state = {'underline': False}
        collected = []

        def local_add(text, anns=None):
            if not text:
                return
            merged = (anns or {}).copy()
            if state['underline']:
                merged['underline'] = True
            collected.extend(self._split_text(text, merged or None))

        _add = add if add is not None else local_add

        ct = child.get('type')

        if ct in ('text', 'html_inline', 'inline_html'):
            raw = child.get('raw', child.get('text', ''))
            # Handle <u>...</u> inline HTML tags for underlines
            parts = re.split(r'(<u>|</u>)', raw)
            for part in parts:
                if part == '<u>':
                    state['underline'] = True
                elif part == '</u>':
                    state['underline'] = False
                elif part:
                    _add(part)

        elif ct == 'strong':
            _add(self._get_raw_text(child), {'bold': True})

        elif ct == 'emphasis':
            _add(self._get_raw_text(child), {'italic': True})

        elif ct == 'codespan':
            _add(self._get_raw_text(child), {'code': True})

        elif ct == 'strikethrough':
            _add(self._get_raw_text(child), {'strikethrough': True})

        elif ct == 'link':
            link_text = self._get_raw_text(child)
            url = child.get('attrs', {}).get('url', '')
            is_valid = self._is_valid_url(url)
            for chunk in self._split_text(link_text):
                if is_valid:
                    chunk['text']['link'] = {'url': url}
                if state['underline']:
                    chunk.setdefault('annotations', {})['underline'] = True
                collected.append(chunk)

        elif ct in ('softbreak', 'linebreak', 'hardbreak'):
            _add('\n')

        elif ct in ('block_text', 'paragraph', 'table_cell'):
            # Recurse into inline-only container nodes
            for sub in child.get('children', []):
                collected.extend(self._rich_text_inline(sub, state, _add))

        else:
            raw = child.get('raw', child.get('text', ''))
            if raw:
                _add(raw)

        return collected

    # ------------------------------------------------------------------
    # Low-level utilities
    # ------------------------------------------------------------------

    def _rich_blocks(self, block_type: str, rich_text: list[dict]) -> list[dict]:
        """
        Build one or more Notion blocks of `block_type` from a rich_text list.
        Splits into multiple blocks if rich_text exceeds 100 items (Notion limit).
        """
        if not rich_text:
            return []
        merged = self._merge_rich_text(rich_text)
        blocks = []
        for i in range(0, len(merged), 100):
            chunk = merged[i:i + 100]
            blocks.append({
                'object': 'block',
                'type': block_type,
                block_type: {'rich_text': chunk},
            })
        return blocks

    def _merge_rich_text(self, items: list[dict]) -> list[dict]:
        """Merge adjacent rich_text objects with identical annotations/links."""
        if not items:
            return []
        merged = []
        for item in items:
            if not merged:
                merged.append(item)
                continue
            last = merged[-1]
            if (last.get('annotations') == item.get('annotations') and
                    last.get('text', {}).get('link') == item.get('text', {}).get('link')):
                new_content = last['text']['content'] + item['text']['content']
                if len(new_content) <= 2000:
                    last['text']['content'] = new_content
                    continue
            merged.append(item)
        return merged

    def _split_text(self, text: str, annotations: dict = None) -> list[dict]:
        """
        Split `text` into ≤2000-char Notion rich_text chunks and strip emojis.
        If `annotations` is an empty dict, omit the key entirely (Notion default).
        """
        if not text:
            return []
        text = emoji.replace_emoji(text, replace='')
        if not text:
            return []
        chunks = []
        for i in range(0, len(text), 2000):
            item = {'type': 'text', 'text': {'content': text[i:i + 2000]}}
            if annotations:
                item['annotations'] = annotations
            chunks.append(item)
        return chunks

    def _is_valid_url(self, url: str) -> bool:
        if not url:
            return False
        try:
            r = urlparse(url)
            return bool(r.scheme) and bool(r.netloc) and r.scheme in ('http', 'https')
        except Exception:
            return False
