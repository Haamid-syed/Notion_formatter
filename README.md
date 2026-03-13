# Notion Formatter 🚀

A production-grade tool to automatically format messy Notion pages into beautifully structured documents using AI.

## ✨ Features

- **OAuth Integration**: Securely connect your Notion workspace.
- **Recursive Block Fetching**: Deeply traverses your Notion pages to capture all content.
- **Gemini AI Formatting**: Leverages Google's Gemini 1.5 Flash to intelligently reorganize text, add headings, bold key terms, and fix formatting without losing meaning.
- **Intelligent Markdown Conversion**: Converts AI output back into native Notion blocks (headings, lists, code blocks with language detection, dividers).
- **Idempotency**: Safely re-run the formatter on the same page; it automatically replaces its previous output.
- **Reliable Networking**: Built-in exponential backoff retries for Notion API rate limits and network stability.

## 🛠 Tech Stack

- **Backend**: Python / Flask
- **LLM**: Google Gemini API
- **Notion SDK**: `notion-client`
- **Markdown Parsing**: `mistune`
- **Reliability**: `tenacity` for retries

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.8+
- A Notion Developer Account ([My Integrations](https://www.notion.so/my-integrations))
- A Google AI Studio API Key ([Get one here](https://aistudio.google.com/app/apikey))

### 2. Setup Environment
Create a `.env` file in the root directory:
```bash
NOTION_CLIENT_ID=your_client_id
NOTION_CLIENT_SECRET=your_client_secret
NOTION_REDIRECT_URI=http://localhost:8080
GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=your_flask_secret_key
```

### 3. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python3 run.py
```
The app will be available at **http://localhost:8080**.

## 📖 Usage
1. Open the app and click **"Connect to Notion"**.
2. Authorize the pages you want the formatter to access.
3. Select a page from your dashboard.
4. Click **"Format Page"**.
5. Your page will be updated in Notion with a structured "AI Formatted Output" section.

## ⚠️ Important Note for Mac Users
If you encounter a `403 Forbidden` error on port 5000, please use port **8080** (default in this app) as macOS often reserves port 5000 for AirPlay Receiver.
