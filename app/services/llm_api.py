import logging
import os
from typing import List, Optional
from openai import OpenAI
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from flask import current_app

logger = logging.getLogger(__name__)

# List of powerful free models on OpenRouter (Verified March 2026)
FREE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free", # Elite 120B model for multi-step tasks
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "deepseek/deepseek-r1:free", # Added DeepSeek reasoning baseline
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "openrouter/free" # Intelligent catch-all fallback
]

class GeminiService:
    """
    Renamed internally to use OpenRouter but kept class name for compatibility.
    Provides robust, multi-model fallback for formatting Notion notes.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        if not self.api_key:
            try:
                # Prioritize OPENROUTER_API_KEY, fallback to GEMINI_API_KEY
                self.api_key = current_app.config.get('OPENROUTER_API_KEY') or current_app.config.get('GEMINI_API_KEY')
            except Exception:
                pass
                
        if self.api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": "http://localhost:8080", # Optional, for OpenRouter rankings
                    "X-Title": "Notion Formatter",
                }
            )
        else:
            self.client = None
            logger.warning("GeminiService (OpenRouter) initialized without an API key")

    def _chunk_text(self, text: str, chunk_size: int = 6000) -> List[str]:
        """Split text into manageable chunks for the LLM."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        current_idx = 0
        while current_idx < len(text):
            end_idx = min(current_idx + chunk_size, len(text))
            if end_idx < len(text):
                newline_idx = text.rfind('\n', current_idx, end_idx)
                if newline_idx != -1 and newline_idx > current_idx:
                    end_idx = newline_idx + 1
            chunks.append(text[current_idx:end_idx])
            current_idx = end_idx
        return chunks

    @retry(
        wait=wait_exponential(multiplier=2, min=4, max=30),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception)
    )
    def _call_llm_with_fallback(self, system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        """Attempts to call models in order until one succeeds or we run out of options."""
        if not self.client:
            raise ValueError("LLM Client not configured. Missing OpenRouter API Key.")

        last_error = None
        for model_id in FREE_MODELS:
            try:
                logger.info(f"Attempting to call OpenRouter model: {model_id}")
                response = self.client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=temperature,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Model {model_id} failed: {e}")
                last_error = e
                continue
        
        raise last_error or Exception("All OpenRouter models failed.")

    def format_text(self, text: str) -> str:
        """Format existing text chunks using OpenRouter."""
        if not text or not text.strip():
            return ""
            
        system_instruction = (
            "You are an expert technical writer, editor, and Notion architect. Your task is to transform "
            "messy, flat text blocks into a beautifully formatted, highly readable Notion document.\n\n"
            "STRICT RULES:\n"
            "1. NOISE REMOVAL: Strip all page numbers, headers, footers, and repeated boilerplate metadata from the input first.\n"
            "2. PRESERVE EVERY WORD: Maintain exactly 100% of the original content wording. Do NOT rephrase, summarize, or 'correct' usage. Your job is ONLY to improve the visual structure.\n"
            "3. AGGRESSIVE ORGANIZATION: Use Markdown headings (## H2, ### H3) extensively to separate main topics.\n"
            "4. SECTION DIVIDERS: Always insert a horizontal ruler (`---`) between logical sections.\n"
            "5. RICH LISTS: Transform lists and related thoughts into bulleted lists (-) or numbered lists (1.).\n"
            "6. EMPHASIS: Liberally use **bolding**, `<u>underlining</u>`, and `~~strikethrough~~` to make the content pop.\n"
            "7. CODE: Wrap technical terms, code excerpts, or logs in EXACTLY triple backticks (```) on their own separate lines, with language identifiers. If you are using code blocks inside other structures like blockquotes, ensure the backticks are on a fresh line.\n"
            "8. TOGGLES: For long lists or detailed sections, you may use collapsible toggles with this EXACT syntax inside a blockquote:\n"
            "   > !toggle YOUR HEADER TITLE HERE\n"
            "   > Your multiline content goes here.\n"
            "   (Note the mandatory newline between the header and the content)\n"
            "9. NO HALLUCINATION: Do NOT add new context, intros, or conclusions that weren't present.\n"
            "10. NO EMOJIS: Do not use or add emojis under any circumstances.\n"
            "11. NO INVALID LINKS: Do NOT generate or create any Markdown links `[text](url)` unless the source text already contained a real, absolute `http://` or `https://` URL. Do NOT create placeholder links."
        )

        chunks = self._chunk_text(text)
        formatted_chunks = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Formatting via OpenRouter (Chunk {i+1}/{len(chunks)})...")
            formatted = self._call_llm_with_fallback(system_instruction, chunk)
            formatted_chunks.append(formatted)
            
        return "\n\n".join(formatted_chunks)

    def clean_extracted_text(self, text: str) -> str:
        """Now handled in the main formatting pass."""
        return text

    def generate_unified_page(self, title: str, user_prompt: str) -> str:
        """Generate a brand new page from scratch via OpenRouter."""
        system_instruction = (
            f"You are creating a new Notion page titled '{title}'.\n\n"
            "STRICT RULES:\n"
            "1. Output exactly and only Markdown format without any conversational wrapper.\n"
            "2. Follow the user's specific instructions for content, structure, and formatting precisely.\n"
            "3. BE CREATIVE AND ARCHITECTURAL: Even if the user's instructions are minimal or vague, do NOT produce a boring list of just headings and bullets. Self-structure the content into a mix of:\n"
            "   - TABLES for comparative data, specifications, or structured lists.\n"
            "   - CALLOUTS/TOGGLES for supplementary notes or detailed breakdowns.\n"
            "   - CODE BLOCKS for technical terms, commands, or snippets.\n"
            "   - AGGRESSIVE BOLDING for scannability.\n"
            "4. Use Markdown headings (## H2, ### H3) for clear organization.\n"
            "5. Use bullet points (-) and numbered lists (1.) for itemization. Do not create empty list items.\n"
            "6. Use EXACTLY triple backticks (```) on their own lines with language identifiers for ALL tech content and code blocks. If inside a toggle, ensure the backticks are on a fresh line starting with '> '.\n"
            "7. For TABLES, use standard Markdown table syntax `| header | header |`. Ensure every cell contains text; if no content is needed, use a single space. Never use emojis in table cells.\n"
            "   CRITICAL: Never put headings (##) on the same line as a table header. Always put a blank line before and after every table.\n"
            "8. For COLLAPSIBLE TOGGLES, you MUST use exactly this syntax snippet as a blockquote:\n"
            "   > !toggle YOUR HEADER TITLE HERE\n"
            "   > Your comprehensive multiline content inside the toggle goes here.\n"
            "   CRITICAL: There MUST be a newline between the '!toggle' header line and the content.\n"
            "9. For NESTED SUBPAGES, prefix the line with `> !page` followed by the subpage title.\n"
            "10. For RICH WORD FORMATTING: Use **bold**, *italics*, `<u>underlines</u>`, and `~~strikethroughs~~` to make the content pop and look premium.\n"
            "11. Insert a thematic break `---` between major sections.\n"
            "12. Generate comprehensive and professional notes that look like a premium Notion architect designed them.\n"
            "13. NO EMOJIS OR FLUFF: Do not use emojis. Do not add conversational intros, outros, or pleasantries. Output only the pure professional document.\n"
            "14. NO INVALID LINKS: Strictly avoid generating Markdown links `[text](url)` unless the URL is a real, absolute, and fully qualified `http://` or `https://` address. Do NOT use fake placeholders or relative paths."
        )
        
        user_content = f"Title: {title}\nInstructions: {user_prompt}"
        return self._call_llm_with_fallback(system_instruction, user_content, temperature=0.7)
