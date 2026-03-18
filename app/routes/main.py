import os
import requests
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, session, redirect, url_for, current_app, request
from notion_client import Client

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    # 1. Handle incoming OAuth code if Notion redirected to root
    code = request.args.get('code')
    if code:
        client_id = current_app.config.get('NOTION_CLIENT_ID')
        client_secret = current_app.config.get('NOTION_CLIENT_SECRET')
        redirect_uri = current_app.config.get('NOTION_REDIRECT_URI')

        token_url = "https://api.notion.com/v1/oauth/token"
        auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri
        }
        
        response = requests.post(token_url, auth=auth, json=data)
        if response.status_code == 200:
            token_data = response.json()
            session['notion_access_token'] = token_data.get('access_token')
            return redirect(url_for('main.index'))
        else:
            current_app.logger.error(f"Failed to exchange code: {response.text}")
            return render_template('index.html', error="Failed to authenticate with Notion.")

    # 2. Existing dashboard logic
    token = session.get('notion_access_token')
    
    if not token:
        return render_template('index.html')
    
    try:
        notion = Client(auth=token)
        # Search for pages the integration has access to
        response = notion.search(
            filter={"value": "page", "property": "object"},
            page_size=100
        )
        pages = response.get('results', [])
        
        # Extract title and id
        formatted_pages = []
        for page in pages:
            page_id = page['id']
            properties = page.get('properties', {})
            title = "Untitled"
            
            # Notion properties structure can vary, try to find the title block
            for prop_name, prop_data in properties.items():
                if prop_data.get('type') == 'title':
                    title_arr = prop_data.get('title', [])
                    if title_arr:
                        title = title_arr[0].get('plain_text', 'Untitled')
                    break

            formatted_pages.append({'id': page_id, 'title': title})
            
        return render_template('dashboard.html', pages=formatted_pages)
        
    except Exception as e:
        current_app.logger.error(f"Error connecting to Notion: {e}")
        # Clear token if invalid
        session.pop('notion_access_token', None)
        return render_template('index.html', error="Failed to connect to Notion. Please try again.")

@bp.route('/about')
def about():
    return render_template('about.html')

@bp.route('/docs')
def docs():
    return render_template('docs.html')

@bp.route('/format/<page_id>', methods=['POST'])
def format_page(page_id):
    from app.services.format_pipeline import FormatPipeline
    
    token = session.get('notion_access_token')
    if not token:
        return redirect(url_for('auth.login'))
        
    pipeline = FormatPipeline(token)
    success = pipeline.run(page_id)
    
    return render_template('result.html', success=success)

@bp.route('/import_file', methods=['POST'])
def import_file():
    from app.services.format_pipeline import FormatPipeline
    from app.services.adapters import FileAdapter
    from app.services.llm_api import GeminiService
    from app.services.notion_api import NotionService
    
    token = session.get('notion_access_token')
    if not token: return redirect(url_for('auth.login'))
    
    title = request.form.get('title')
    file = request.files.get('file')
    if not file or file.filename == "":
        return render_template('result.html', success=False)
        
    # If no title provided, use filename without extension
    if not title:
        title = os.path.splitext(file.filename)[0].replace('_', ' ').title()

    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config.get('UPLOAD_FOLDER', '/tmp'), filename)
    file.save(filepath)
    
    try:
        # 1. Create the new page at workspace root
        notion_service = NotionService(token)
        new_page = notion_service.create_page(title, None)
        new_page_id = new_page['id']
        
        # 2. Run the pipeline with the file adapter targeting the new page
        adapter = FileAdapter(filepath, filename, GeminiService())
        pipeline = FormatPipeline(token)
        success = pipeline.run_with_adapter(adapter, new_page_id)
        
        return render_template('result.html', success=success)
    except Exception as e:
        current_app.logger.error(f"Failed to import and format file: {e}", exc_info=True)
        return render_template('result.html', success=False)
    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

@bp.route('/create_page', methods=['POST'])
def create_page():
    from app.services.format_pipeline import FormatPipeline
    from app.services.adapters import WorkspacePageCreator
    from app.services.llm_api import GeminiService
    from app.services.notion_api import NotionService

    token = session.get('notion_access_token')
    if not token: return redirect(url_for('auth.login'))
    
    title = request.form.get('title')
    prompt = request.form.get('prompt', '')
    
    if not title:
        return render_template('result.html', success=False)
        
    try:
        # Create the blank page at workspace root by passing None as parent
        notion_service = NotionService(token)
        new_page = notion_service.create_page(title, None)
        new_page_id = new_page['id']
        
        # Now run the pipeline with the specific creator adapter targeting the new page
        adapter = WorkspacePageCreator(title, prompt, notion_service, GeminiService())
        pipeline = FormatPipeline(token)
        success = pipeline.run_with_adapter(adapter, new_page_id)
        
        return render_template('result.html', success=success)
        
    except Exception as e:
        current_app.logger.error(f"Failed to create new page: {e}", exc_info=True)
        return render_template('result.html', success=False)
