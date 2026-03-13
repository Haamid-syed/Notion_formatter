import logging
from google import genai
from google.genai import types
from tenacity import retry, wait_exponential, stop_after_attempt
from flask import current_app

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        if not self.api_key:
            # Fallback to app config if available when running within app context
            try:
                self.api_key = current_app.config.get('GEMINI_API_KEY')
            except Exception:
                pass
                
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("GeminiService initialized without an API key")

    def _chunk_text(self, text: str, chunk_size: int = 4000) -> list[str]:
        """Safely split strings into chunks mostly by line breaks to avoid cutting sentences."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        current_idx = 0
        
        while current_idx < len(text):
            end_idx = min(current_idx + chunk_size, len(text))
            
            if end_idx < len(text):
                # Try to find a line break to split safely
                newline_idx = text.rfind('\n', current_idx, end_idx)
                if newline_idx != -1 and newline_idx > current_idx:
                    end_idx = newline_idx + 1 # Include the newline
            
            chunks.append(text[current_idx:end_idx])
            current_idx = end_idx
            
        return chunks

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def _call_gemini(self, text: str) -> str:
        """Call Gemini API to format a single chunk of text."""
        if not self.client:
            raise ValueError("Cannot call Gemini API: API key not configured")
            
        system_instruction = (
            "You are an expert technical writer, editor, and Notion architect. Your task is to transform "
            "messy, flat text blocks into a beautifully formatted, highly readable Notion document.\n\n"
            "STRICT RULES:\n"
            "1. NO HALLUCINATION: Maintain exactly 100% of the original information. Do NOT add new context, thoughts, introductions, or conclusions that weren't present in the source material.\n"
            "2. AGGRESSIVE ORGANIZATION: Use Markdown headings (## H2, ### H3) extensively to separate main topics.\n"
            "3. SECTION DIVIDERS: Always insert a horizontal ruler (`---` on its own line) at the very end of each logical section or before a new Heading 2.\n"
            "4. RICH LISTS: Transform comma-separated lists, scattered but related thoughts, and flat arrays into bulleted lists (-) or numbered lists (1.). Every bullet point must contain the original text (do not create empty bullets).\n"
            "5. EMPHASIS: Liberally use **bolding** to highlight key terms, metrics, and topic sentences to make the page highly scannable.\n"
            "6. CODE: Wrap technical terms, code excerpts, logs, or JSON in triple backticks. ALWAYS specify the programming language (e.g., ```python, ```javascript, ```json) if known, otherwise use ```text.\n"
            "7. CLEANUP: Only fix egregious formatting or grammar mistakes to maintain the original meaning."
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            )
        )
        return response.text

    def format_text(self, text: str) -> str:
        """Format the full text, processing in chunks if necessary."""
        if not text or not text.strip():
            return ""
            
        chunks = self._chunk_text(text)
        formatted_chunks = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Formatting text chunk {i+1} of {len(chunks)}")
            formatted = self._call_gemini(chunk)
            formatted_chunks.append(formatted)
            
        # Join chunks with newlines
        return "\n\n".join(formatted_chunks)
