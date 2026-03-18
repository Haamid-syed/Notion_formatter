import logging
from notion_client import Client
from notion_client.errors import APIResponseError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)

class NotionService:
    def __init__(self, access_token: str):
        self.client = Client(auth=access_token)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(APIResponseError)
    )
    def _fetch_children_page(self, block_id: str, cursor: str = None):
        """Fetch a single page of children blocks, with retries."""
        kwargs = {"block_id": block_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        return self.client.blocks.children.list(**kwargs)

    def get_all_blocks_recursive(self, block_id: str):
        """
        Recursively fetch all blocks for a given block_id (which can be a page_id).
        Attaches nested blocks to a 'children_blocks' key on the parent block.
        """
        blocks = []
        has_more = True
        next_cursor = None

        try:
            while has_more:
                response = self._fetch_children_page(block_id, next_cursor)
                current_blocks = response.get('results', [])
                
                for block in current_blocks:
                    if block.get('has_children'):
                        # Recursively fetch children
                        children = self.get_all_blocks_recursive(block['id'])
                        block['children_blocks'] = children
                    blocks.append(block)

                has_more = response.get('has_more', False)
                next_cursor = response.get('next_cursor')

        except Exception as e:
            logger.error(f"Failed to fetch blocks for {block_id}: {e}")
            raise

        return blocks

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
    def append_blocks(self, block_id: str, blocks: list) -> dict:
        """Append blocks as children to the specified block."""
        return self.client.blocks.children.append(block_id=block_id, children=blocks)

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
    def delete_block(self, block_id: str):
        """Delete (archive) a block."""
        return self.client.blocks.delete(block_id=block_id)

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
    def create_page(self, title: str, parent_page_id: str = None) -> dict:
        """Create a new page. If parent_page_id is None, tries to create in workspace root."""
        if parent_page_id:
            logger.info(f"Creating new page '{title}' under parent {parent_page_id}")
            parent = {"type": "page_id", "page_id": parent_page_id}
        else:
            logger.info(f"Creating new page '{title}' at workspace root")
            # For public integrations, workspace root is possible.
            # For internal ones, they often must be shared a specific page.
            parent = {"type": "workspace", "workspace": True}
        
        new_page = self.client.pages.create(
            parent=parent,
            properties={
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        )
        return new_page

    def extract_text(self, blocks: list) -> str:
        """Recursively extract plain text from an array of blocks."""
        extracted = []
        
        for block in blocks:
            block_type = block.get('type')
            if not block_type:
                continue
                
            block_content = block.get(block_type, {})
            rich_texts = block_content.get('rich_text', [])
            
            # Combine all plain text fragments in this block
            text = "".join([rt.get('plain_text', '') for rt in rich_texts])
            if text:
                extracted.append(text)
                
            # Recurse if children were fetched
            children = block.get('children_blocks', [])
            if children:
                child_text = self.extract_text(children)
                if child_text:
                    extracted.append(child_text)
                    
        return "\n\n".join(extracted)
