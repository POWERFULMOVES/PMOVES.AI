"""
PMOVES Tokenism Simulator

Token economy simulation service for PMOVES.AI.

Integrations:
- NATS message bus (port 4222)
- TensorZero LLM gateway (port 3030)
- Supabase (port 3010)
- Prometheus metrics (port 9090)

CHIT/Geometry Bus:
- Publishes to tokenism.cgp.ready.v1
- Hyperbolic visualization of wealth distribution
"""

import logging
import os
import sys
from pathlib import Path

from flask import Flask
from flask_cors import CORS
import structlog

# Add service directory to path for imports
service_dir = Path(__file__).parent
sys.path.insert(0, str(service_dir))

from config import config
from api.simulation import simulation_bp

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Set up standard logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
)

logger = structlog.get_logger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.secret_key

    # Enable CORS for all routes
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Register blueprints
    app.register_blueprint(simulation_bp)

    # Root endpoint
    @app.route('/')
    def index():
        return {
            'service': 'PMOVES Tokenism Simulator',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'health': '/healthz',
                'metrics': '/metrics',
                'simulate': '/api/v1/simulate',
                'scenarios': '/api/v1/scenarios',
                'contracts': '/api/v1/contracts',
            },
            'integrations': {
                'nats': config.nats.url,
                'tensorzero': config.tensorzero.url,
                'supabase': config.supabase.url,
            },
        }, 200

    @app.route('/healthz')
    def healthz():
        return {'status': 'ok'}, 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error('Internal error', error=str(error))
        return {'error': 'Internal server error'}, 500

    logger.info(
        'Tokenism Simulator starting',
        host=config.host,
        port=config.port,
        debug=config.debug,
    )

    return app


def main():
    """Run the Flask application."""
    app = create_app()

    # Production: gunicorn handles this
    # Development: run directly
    if os.getenv('FLASK_ENV') == 'development':
        app.run(
            host=config.host,
            port=config.port,
            debug=config.debug,
        )
    else:
        # For gunicorn
        app.run(host='0.0.0.0', port=8100)


if __name__ == '__main__':
    main()
