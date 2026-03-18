import logging
from app.services.notion_api import NotionService
from app.services.llm_api import GeminiService
from app.services.markdown_converter import MarkdownConverter
from app.services.adapters import BaseAdapter, NotionAdapter

logger = logging.getLogger(__name__)

# The idempotent marker we inject and search for
MARKER_TEXT = "--- AI Formatted Output ---"

class FormatPipeline:
    def __init__(self, token: str):
        self.notion = NotionService(token)
        self.gemini = GeminiService()
        self.converter = MarkdownConverter()
        
    def run(self, page_id: str) -> bool:
        """Backwards compatibility for existing route: uses NotionAdapter."""
        existing_blocks = self.notion.get_all_blocks_recursive(page_id)
        if not existing_blocks:
            return False
            
        # Optional: We could cleanly extract `clean_blocks` here to avoid double fetch
        # but run_with_adapter inherently fetches existing_blocks and cleans them.
        # It then calls adapter.fetch_text(). If we just pass NotionAdapter, it will 
        # double fetch blocks. Let's optimize run_with_adapter to support providing pristine blocks.
        return self.run_with_adapter(NotionAdapter(self.notion, page_id), page_id)
        
    def run_with_adapter(self, adapter: BaseAdapter, target_page_id: str) -> bool:
        """Run the formatting pipeline taking input from a generic adapter."""
        try:
            logger.info(f"Starting formatting pipeline for target page: {target_page_id}")
            
            # 1. Fetch current blocks in the target page
            existing_blocks = self.notion.get_all_blocks_recursive(target_page_id)
            if existing_blocks is None:
                logger.warning(f"Could not fetch blocks for page {target_page_id}")
                return False
                
            # 2. Extract text from the adapter using current blocks if needed
            if isinstance(adapter, NotionAdapter):
                adapter._blocks = existing_blocks
                
            raw_text = adapter.fetch_text()
            if not raw_text or not raw_text.strip():
                logger.info("Extracted text is empty. Nothing to format.")
                return True

            # 3. DELETE all existing blocks if it's an existing page format request
            # This ensures the page is wiped clean before the new formatted content is added
            if isinstance(adapter, NotionAdapter):
                logger.info(f"Clearing all existing blocks from page {target_page_id}...")
                for block in existing_blocks:
                    try:
                        self.notion.delete_block(block['id'])
                    except Exception as e:
                        logger.warning(f"Could not delete block {block['id']}: {e}")

            # 4. Process with Gemini
            if getattr(adapter, 'already_formatted', False):
                logger.info("Content is already formatted. Skipping Gemini formatting step.")
                formatted_markdown = raw_text
            else:
                logger.info("Sending text to Gemini for formatting...")
                formatted_markdown = self.gemini.format_text(raw_text)
            
            if not formatted_markdown.strip():
                logger.warning("Gemini returned empty text.")
                return False
                
            # 5. Convert Markdown to Notion Blocks
            logger.info("Converting Markdown to Notion Blocks...")
            new_notion_blocks = self.converter.convert_fast(formatted_markdown)
            
            # 6. Append in batches of 100
            batch_size = 100
            for i in range(0, len(new_notion_blocks), batch_size):
                batch = new_notion_blocks[i:i + batch_size]
                logger.info(f"Appending batch {i // batch_size + 1} ({len(batch)} blocks)...")
                self.notion.append_blocks(target_page_id, batch)
                
            logger.info(f"Successfully formatted page {target_page_id}")
            return True
            
        except Exception as e:
            logger.error(f"Pipeline failed for target page {target_page_id}: {e}", exc_info=True)
            return False
