# Notion Formatter

A professional tool that leverages AI to transform messy text and documents into structured, native Notion pages. 

The application is live and accessible at: 
[https://notion-formatter-haamids-projects.vercel.app/](https://notion-formatter-haamids-projects.vercel.app/)

## How to Use

### 1. Authenticate with Notion
Visit the site and click the "Authenticate" button. You will be redirected to Notion where you can choose which specific pages or workspaces you want to grant the app access to.

### 2. Format Existing Notion Pages
Once logged in, the dashboard will list the pages you've shared. 
- Find the document you want to organize.
- Click the "Format" button.
- The system will fetch the text, remove noise (page numbers, duplicate headers, boilerplate), and append a perfectly formatted Markdown version back into the same Notion page.

### 3. Create a New Document from a Prompt
Use the "New Note" section on the dashboard to generate a page from scratch:
- Enter a Title and a brief description (Prompt).
- Our AI will design a comprehensive, well-structured document (with tables, lists, and headers) and create it instantly in your workspace.

### 4. Import from PDF or DOCX
If you have a local document that needs to be moved to Notion:
- Upload your .pdf or .docx file in the import section.
- The tool will extract the text, clean up the formatting via AI, and create a brand-new page in your Notion workspace with the converted content.

## Key Features

- **Structural Noise Removal**: Automatically detects and strips out headers, footers, and other duplicate metadata from messy notes.
- **Smart Code Blocks**: Identifies technical snippets and formats them with native Notion syntax highlighting.
- **AI Fallbacks**: Uses a resilient model-fallback system (via OpenRouter) to ensure formatting results are always high-quality and logically structured.
- **Session-Based Security**: Authorizations are handled securely via OAuth 2.0, ensuring your workspace remains private and your content stays within your control.

## Technology Stack

- **Framework**: Python 3.13 / [Flask](https://flask.palletsprojects.com/)
- **Integration**: [Notion SDK](https://github.com/makenotion/notion-sdk-py) for page and block management.
- **AI Gateway**: [OpenRouter API](https://openrouter.ai/) for orchestrating LLMs (Nemotron, Llama, and others).
- **Document Processing**: [Mistune 3.0](https://github.com/lepture/mistune) for Markdown parsing and block conversion.
- **File Extraction**: [PDFPlumber](https://github.com/jsvine/pdfplumber) and [Python-Docx](https://python-docx.readthedocs.io/) for document parsing.
- **Frontend & Motion**: Vanilla HTML5/CSS3, [GSAP](https://greensock.com/gsap/) for UI transitions, and [Lenis](https://lenis.darkroom.engineering/) for smooth scrolling.
- **Hosting**: [Vercel](https://vercel.com/) Serverless Python environment.

---

Built for reliable, clean Notion workspace management.
