import os
import re
from flask import Flask, request, render_template_string, jsonify
from notion_client import Client as NotionClient
import requests
from dotenv import load_dotenv

# Load .env
load_dotenv()

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

# Use GROQ_API_KEY for Groq API
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not NOTION_TOKEN or not GROQ_API_KEY:
    raise ValueError("Set NOTION_TOKEN and GROQ_API_KEY in .env")

# Initialize Notion client
notion = NotionClient(auth=NOTION_TOKEN)



app = Flask(__name__)

# Helpers
def extract_page_id(url: str) -> str:
    match = re.search(r"[0-9a-f]{32}", url)
    if not match:
        raise ValueError("Invalid Notion URL")
    return match.group(0)

def fetch_plain_text(page_id: str) -> str:
    blocks = []
    cursor = None
    while True:
        res = notion.blocks.children.list(block_id=page_id, start_cursor=cursor)
        for block in res.get("results", []):
            btype = block["type"]
            content = block.get(btype, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in content])
            if text.strip():
                blocks.append(text)
        cursor = res.get("next_cursor")
        if not cursor:
            break
    return "\n".join(blocks)

def markdown_to_blocks(md: str):
    lines = md.split("\n")
    blocks = []
    in_code = False
    code_lines = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": "\n".join(code_lines)}
                        }],
                        "language": "plain text"
                    }
                })
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            continue

        if line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                }
            })
        elif line.startswith("- "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                }
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line}}]
                }
            })

    return blocks



def format_text_with_groq(text: str) -> str:
    prompt = f"""You are a STRICT TEXT FORMATTER.

This is NOT a rewriting task.

ABSOLUTE RULES (violations are errors):
1. You may NOT add, remove, or replace words.
2. You may NOT change word order within a sentence.
3. You may ONLY:
   - Add or remove punctuation.
   - Change capitalization.
   - Insert line breaks.
   - Insert markdown syntax (##, -, ```).
4. If you cannot format something without changing words, leave it unchanged.
5. Code blocks MUST be copied verbatim, character-for-character.

Formatting rules:
- Use ## only for clear section headers already implied by the text.
- Use '-' for unordered lists only (never numbered lists).
- Wrap code in triple backticks with no language tag.
- Do NOT introduce numbered lists.

Validation rule:
- Output must contain at least 90% of the original words unchanged.

Output ONLY markdown. No explanations.

TEXT:
<BEGIN>
{text}
<END>
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-8b-instant",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }
    resp = requests.post(url, headers=headers, json=data)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        try:
            err = resp.json()
            raise Exception(f"Groq API error: {err.get('error', {}).get('message', str(err))}")
        except Exception:
            raise Exception(f"Groq API error: {resp.text}")
    result = resp.json()
    return result["choices"][0]["message"]["content"]

def append_blocks_to_notion(page_id: str, blocks):
    notion.blocks.children.append(
        block_id=page_id,
        children=[{"object":"block","type":"divider","divider":{}}]
    )
    for i in range(0, len(blocks), 10):
        notion.blocks.children.append(
            block_id=page_id,
            children=blocks[i:i+10]
        )

# Flask routes
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Notion Formatter</title></head>
<body>
<h2>Notion Formatter</h2>
<form id="formatForm">
  <input type="text" name="notionUrl" placeholder="Enter Notion page URL" required size="50"/>
  <button type="submit">Format & Append</button>
</form>
<div id="result"></div>
<script>
document.getElementById("formatForm").onsubmit = async e => {
  e.preventDefault();
  const url = e.target.notionUrl.value;
  document.getElementById("result").innerText = "Processing...";
  const resp = await fetch("/format", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({notionUrl: url})
  });
  const data = await resp.json();
  document.getElementById("result").innerText = data.success
    ? "Success! Appended formatted output."
    : "Error: " + data.error;
};
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/format", methods=["POST"])
def format_endpoint():
    try:
        data = request.get_json()
        notion_url = data.get("notionUrl")
        if not notion_url:
            return jsonify({"error":"No Notion URL provided"}), 400

        page_id = extract_page_id(notion_url)
        raw_text = fetch_plain_text(page_id)
        if not raw_text.strip():
            return jsonify({"error":"Page has no text"}), 400

        formatted_md = format_text_with_groq(raw_text)
        blocks = markdown_to_blocks(formatted_md)
        append_blocks_to_notion(page_id, blocks)
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=3000, debug=True)
