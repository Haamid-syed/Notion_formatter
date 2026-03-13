import mistune

class MarkdownConverter:
    def __init__(self):
        # We use the AST renderer to walk the tree instead of generating HTML
        self.markdown = mistune.create_markdown(renderer='ast')

    def convert(self, markdown_text: str) -> list[dict]:
        """Convert a markdown string into a list of Notion block dictionaries."""
        if not markdown_text:
            return []
            
        ast = self.markdown(markdown_text)
        blocks = []
        
        for node in ast:
            block = self._map_ast_to_notion_block(node)
            if block:
                blocks.append(block)
                
        return blocks
        
    def _map_ast_to_notion_block(self, node: dict) -> dict:
        """Map a mistune AST node to a Notion API block dictionary."""
        node_type = node.get('type')
        
        if node_type == 'heading':
            level = min(max(node.get('attrs', {}).get('level', 1), 1), 3) # Notion only supports H1-H3
            heading_type = f'heading_{level}'
            return {
                "object": "block",
                "type": heading_type,
                heading_type: {
                    "rich_text": self._rich_text_from_node_children(node)
                }
            }
            
        elif node_type == 'paragraph':
            return {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": self._rich_text_from_node_children(node)
                }
            }
            
        elif node_type == 'list':
            list_children = node.get('children', [])
            list_items = []
            
            # Since Mistune wraps list items, we process them individually
            # However, Notion requires items individually, not grouped in a 'list' wrapper
            # For simplicity in this flat mapping, we return the children parsed out.
            # But the orchestrator expects a single block dict. So we need to flatten the list items out
            # into the main flow.
            # To handle this cleanly without rewriting the architecture deeply, we'll
            # return a special 'paragraph' if we can't flatten gracefully, 
            # or just return the bulleted list item if it's a list item node type.
            # Mistune AST structure: {'type': 'list', 'children': [{'type': 'list_item', 'children': [...]}]}
            pass # handled broadly below: list parent returns children recursively
            
        elif node_type == 'list_item':
            return {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": self._rich_text_from_node_children(node)
                }
            }
            
        elif node_type == 'block_code':
            info = node.get('attrs', {}).get('info', '')
            language = info.lower() if info else "plain text"
            
            # Simple validation list based on Notion's common languages
            # Notion is strict, so we'll fallback to "plain text" if it's not a common one
            # The API will return an error if we send something they don't support.
            supported = [
                "abap", "arduino", "bash", "basic", "c", "c#", "c++", "clojure", "coffeescript", "css", "dart", "diff", "docker", "elixir", "elm", "erlang", "f#", "flow", "fortran", "gherkin", "glsl", "go", "graphql", "groovy", "haskell", "html", "java", "javascript", "json", "julia", "kotlin", "latex", "less", "lisp", "lua", "makefile", "markdown", "matlab", "mermaid", "nix", "objective-c", "ocaml", "pascal", "perl", "php", "plain text", "powershell", "prolog", "protobuf", "python", "r", "reason", "ruby", "rust", "sass", "scala", "scheme", "scss", "shell", "sql", "swift", "toml", "typescript", "vb.net", "verilog", "vhdl", "visual basic", "webassembly", "xml", "yaml"
            ]
            
            if language not in supported:
                # Handle some common aliases or minor mismatches
                if language == "js": language = "javascript"
                elif language == "ts": language = "typescript"
                elif language == "py": language = "python"
                elif language == "sh": language = "shell"
                else: language = "plain text"
                
            return {
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": node.get('raw', '')}
                    }],
                    "language": language
                }
            }
            
        elif node_type == 'block_quote':
            return {
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": self._rich_text_from_node_children(node)
                }
            }
            
        elif node_type == 'blank_line':
            return None
            
        elif node_type == 'thematic_break':
            return {
                "object": "block",
                "type": "divider",
                "divider": {}
            }
            
        # Default fallback: treat as paragraph with its raw content
        raw_text = node.get('raw', node.get('text', str(node)))
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": raw_text}}]
            }
        }

    def _rich_text_from_node_children(self, node: dict) -> list[dict]:
        """Extract rich text objects from node children or text/raw fields."""
        children = node.get('children', [])
        rich_texts = []
        
        if not children and 'text' in node:
            rich_texts.append({
                "type": "text",
                "text": {"content": node['text']}
            })
            return rich_texts
            
        for child in children:
            child_type = child.get('type')
            if child_type == 'text':
                rich_texts.append({
                    "type": "text",
                    "text": {"content": child.get('raw', child.get('text', ''))}
                })
            elif child_type == 'strong':
                rich_texts.append({
                    "type": "text",
                    "text": {"content": child.get('children', [{}])[0].get('raw', '')},
                    "annotations": {"bold": True}
                })
            elif child_type == 'emphasis':
                rich_texts.append({
                    "type": "text",
                    "text": {"content": child.get('children', [{}])[0].get('raw', '')},
                    "annotations": {"italic": True}
                })
            elif child_type == 'codespan':
                rich_texts.append({
                    "type": "text",
                    "text": {"content": child.get('raw', '')},
                    "annotations": {"code": True}
                })
            elif child_type == 'link':
                link_text = child.get('children', [{}])[0].get('raw', 'link')
                rich_texts.append({
                    "type": "text",
                    "text": {
                        "content": link_text,
                        "link": {"url": child.get('attrs', {}).get('url', '#')}
                    }
                })
            elif child_type in ('block_text', 'paragraph'):
                rich_texts.extend(self._rich_text_from_node_children(child))
            # Nested fallbacks could go here
            else:
                raw_text = child.get('raw', child.get('text', ''))
                if raw_text:
                    rich_texts.append({
                        "type": "text",
                        "text": {"content": raw_text}
                    })

        if not rich_texts:
            rich_texts = [{"type": "text", "text": {"content": " "}}]
            
        # Notion has a 2000 length limit per block rich text object content
        # For simplicity, we truncate here if a single node gets too large
        for rt in rich_texts:
            if len(rt['text']['content']) > 2000:
                rt['text']['content'] = rt['text']['content'][:1995] + "..."
                
        return rich_texts

    def convert_fast(self, markdown_text: str) -> list[dict]:
        """
        Flatten nested AST lists before processing.
        Mistune lists contain list_item children. We need to lift list_item into the top level.
        """
        if not markdown_text:
            return []
            
        ast = self.markdown(markdown_text)
        flattened_ast = []
        
        def flatten_nodes(nodes):
            for node in nodes:
                node_type = node.get('type')
                if node_type == 'list':
                    # Unpack list items directly
                    flatten_nodes(node.get('children', []))
                else:
                    flattened_ast.append(node)
                    
        flatten_nodes(ast)
        
        blocks = []
        for node in flattened_ast:
            block = self._map_ast_to_notion_block(node)
            if block:
                blocks.append(block)
                
        return blocks
