import os
import requests
import urllib.parse
from flask import Blueprint, redirect, request, session, current_app, url_for, flash

bp = Blueprint('auth', __name__)

@bp.route('/login')
def login():
    client_id = current_app.config.get('NOTION_CLIENT_ID')
    redirect_uri = current_app.config.get('NOTION_REDIRECT_URI')
    
    if not client_id or not redirect_uri:
        return "Missing Notion OAuth config (NOTION_CLIENT_ID or NOTION_REDIRECT_URI). Please add them to your Vercel Environment Variables.", 500

    client_id = client_id.strip()
    redirect_uri = redirect_uri.strip()

    encoded_redirect = urllib.parse.quote(redirect_uri, safe='')
    notion_auth_url = (
        f"https://api.notion.com/v1/oauth/authorize?"
        "client_id=" + client_id + "&"
        "redirect_uri=" + encoded_redirect + "&"
        "response_type=code&"
        "owner=user"
    )
    current_app.logger.info(f"Generated Notion Auth URL: {notion_auth_url}")
    return redirect(notion_auth_url)

@bp.route('/logout')
def logout():
    session.pop('notion_access_token', None)
    return redirect(url_for('main.index'))
