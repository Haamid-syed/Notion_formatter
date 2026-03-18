import logging
from typing import Optional
import docx
import pdfplumber

logger = logging.getLogger(__name__)

class BaseAdapter:
    def fetch_text(self) -> str:
        """Return raw text to be processed by the LLM."""
        raise NotImplementedError

class NotionAdapter(BaseAdapter):
    def __init__(self, notion_service, page_id: str, blocks=None):
        self.notion_service = notion_service
        self.page_id = page_id
        self._blocks = blocks if blocks is not None else []
        
    def fetch_text(self) -> str:
        """Fetch all blocks from the Notion page and extract text."""
        logger.info(f"Fetching blocks for page {self.page_id}")
        if not self._blocks:
            self._blocks = self.notion_service.get_all_blocks_recursive(self.page_id)
        if not self._blocks:
            return ""
            
        return self.notion_service.extract_text(self._blocks)
        
    def get_blocks(self):
        """Return the fetched blocks. Useful for idempotency cleanup later."""
        return self._blocks

class FileAdapter(BaseAdapter):
    def __init__(self, file_path: str, filename: str, gemini_service=None):
        self.file_path = file_path
        self.filename = filename
        self.gemini_service = gemini_service
        
    def fetch_text(self) -> str:
        """Extract text from DOCX or PDF and optionally pre-filter it."""
        logger.info(f"Extracting text from {self.filename}")
        raw_text = ""
        
        try:
            if self.filename.lower().endswith('.docx'):
                doc = docx.Document(self.file_path)
                raw_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            elif self.filename.lower().endswith('.pdf'):
                with pdfplumber.open(self.file_path) as pdf:
                    pages_text = []
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            pages_text.append(extracted)
                    raw_text = "\n".join(pages_text)
            else:
                logger.error(f"Unsupported file format: {self.filename}")
                return ""
                
            # Return raw text. The pipeline's format pass will handle noise removal.
            return raw_text
                
        except Exception as e:
            logger.error(f"Failed to read file {self.filename}: {e}", exc_info=True)
            return ""

class WorkspacePageCreator(BaseAdapter):
    def __init__(self, title: str, prompt: str, notion_service, gemini_service):
        self.title = title
        self.prompt = prompt
        self.notion_service = notion_service
        self.gemini_service = gemini_service
        self.created_page_id = None
        self.already_formatted = True
        
    def fetch_text(self) -> str:
        """Generates rich markdown from the given title and unified user prompt."""
        logger.info(f"Generating unified page content for: {self.title}")
        try:
            return self.gemini_service.generate_unified_page(self.title, self.prompt)
        except Exception as e:
            logger.error(f"Failed to generate workspace page text for {self.title}: {e}", exc_info=True)
            return ""
