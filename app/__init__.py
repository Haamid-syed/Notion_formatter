import logging
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# limiter = Limiter(
#     key_func=get_remote_address,
#     default_limits=["200 per day", "50 per hour"]
# )

def create_app():
    # Configure logging to stdout
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    # limiter.init_app(app)

    # Register blueprints (to be created later)
    from app.routes import auth, main
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)

    return app
