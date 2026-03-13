import logging
from app.services.notion_api import NotionService
from app.services.llm_api import GeminiService
from app.services.markdown_converter import MarkdownConverter

logger = logging.getLogger(__name__)

# The idempotent marker we inject and search for
MARKER_TEXT = "--- AI Formatted Output ---"

class FormatPipeline:
    def __init__(self, token: str):
        self.notion = NotionService(token)
        self.gemini = GeminiService()
        self.converter = MarkdownConverter()
        
    def run(self, page_id: str) -> bool:
        """Run the full formatting pipeline for a given page."""
        try:
            logger.info(f"Starting formatting pipeline for page: {page_id}")
            
            # 1. Fetch current blocks
            blocks = self.notion.get_all_blocks_recursive(page_id)
            if not blocks:
                logger.warning(f"No blocks found for page {page_id}")
                return False
                
            # 2. Check for idempotency marker and delete previous outputs
            marker_found = False
            clean_blocks = []
            
            for block in blocks:
                # Identify if block is a marker
                if not marker_found:
                    is_marker = False
                    block_type = block.get('type')
                    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3']:
                        rt = block.get(block_type, {}).get('rich_text', [])
                        text = "".join([t.get('plain_text', '') for t in rt]).strip()
                        if text == MARKER_TEXT:
                            is_marker = True
                            
                    if is_marker:
                        marker_found = True
                        logger.info(f"Idempotency marker found at block {block['id']}. Cleaning up old output...")
                        self.notion.delete_block(block['id'])
                        continue # Skip this block
                        
                    # Still pristine original blocks
                    clean_blocks.append(block)
                else:
                    # We are past the marker, meaning these are generated chunks to delete
                    try:
                        self.notion.delete_block(block['id'])
                    except Exception as e:
                        logger.warning(f"Could not delete old block {block['id']}: {e}")
                        
            # 3. Extract text from the pristine blocks
            raw_text = self.notion.extract_text(clean_blocks)
            if not raw_text.strip():
                logger.info("Extracted text is empty. Nothing to format.")
                return True
                
            # 4. Process with Gemini
            logger.info("Sending text to Gemini for formatting...")
            formatted_markdown = self.gemini.format_text(raw_text)
            
            if not formatted_markdown.strip():
                logger.warning("Gemini returned empty text.")
                return False
                
            # 5. Convert Markdown to Notion Blocks
            logger.info("Converting Markdown to Notion Blocks...")
            new_notion_blocks = self.converter.convert_fast(formatted_markdown)
            
            # Prepend the marker block
            marker_block = {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": MARKER_TEXT}
                        }
                    ]
                }
            }
            new_notion_blocks.insert(0, marker_block)
            
            # 6. Append in batches of 100
            batch_size = 100
            for i in range(0, len(new_notion_blocks), batch_size):
                batch = new_notion_blocks[i:i + batch_size]
                logger.info(f"Appending batch {i // batch_size + 1} ({len(batch)} blocks)...")
                self.notion.append_blocks(page_id, batch)
                
            logger.info(f"Successfully formatted page {page_id}")
            return True
            
        except Exception as e:
            logger.error(f"Pipeline failed for page {page_id}: {e}", exc_info=True)
            return False
