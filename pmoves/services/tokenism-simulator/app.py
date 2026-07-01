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

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path

from flask import Flask
from flask_cors import CORS
import structlog

# Add service directory to path for imports
service_dir = Path(__file__).parent
sys.path.insert(0, str(service_dir))

from config import config
from api.simulation import simulation_bp
from api.contracts import contracts_bp
from nats_consumer import start_nats_consumer

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


# Guard so we only spawn the NATS consumer thread once per process
# (matters under gunicorn preload and Flask debug-reload scenarios).
_nats_consumer_started = False
_nats_consumer_lock = threading.Lock()


def _spawn_nats_consumer() -> None:
    """Launch the CGP -> BPM consumer in a daemon asyncio thread.

    Idempotent: safe to call multiple times (e.g. from gunicorn workers).
    The consumer owns its own retry envelope and will not raise back to
    the Flask app, so this never blocks startup.
    """
    global _nats_consumer_started
    with _nats_consumer_lock:
        if _nats_consumer_started:
            return
        _nats_consumer_started = True

    def _run_nats() -> None:
        try:
            asyncio.run(start_nats_consumer())
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'NATS consumer thread exited unexpectedly', error=str(exc)
            )

    threading.Thread(
        target=_run_nats, name='tokenism-nats-consumer', daemon=True
    ).start()
    logger.info('NATS consumer thread started (geometry.cgp.v1 -> tokenism.prosodic.bpm.v1)')


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.secret_key

    # Enable CORS with configurable allowed origins (strip whitespace)
    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            'ALLOWED_ORIGINS',
            'http://localhost:3000,http://localhost:8080,http://localhost:4000'
        ).split(',')
        if origin.strip()
    ]
    CORS(app, resources={r"/*": {"origins": allowed_origins}})

    # Register blueprints
    app.register_blueprint(simulation_bp)
    app.register_blueprint(contracts_bp)

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

    # Subscribe to geometry.cgp.v1 in a background asyncio thread so the
    # rhythm tracker has live BPM input from the voice synthesis pipeline.
    _spawn_nats_consumer()

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
