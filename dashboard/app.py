# dashboard/app.py
"""
GitOps Dashboard
Real-time monitoring dashboard for the Smart GitOps Platform.
"""
from flask import Flask, render_template, jsonify
import requests
import logging

app = Flask(__name__)
logger = logging.getLogger('gitops.dashboard')

CONTROLLER_URL = 'http://localhost:8080'


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/api/dashboard-data')
def dashboard_data():
    """Proxy endpoint to get data from the controller."""
    try:
        response = requests.get(
            f'{CONTROLLER_URL}/api/status', timeout=5
        )
        if response.status_code == 200:
            return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
    
    return jsonify({'error': 'Cannot connect to controller'}), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001, debug=True)