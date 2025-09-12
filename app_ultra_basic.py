"""
Ultra-Basic Bot Service - 502 Error Emergency Fix
Absolute minimal Flask app with zero dependencies
"""
from flask import Flask

# Create the most basic Flask app possible
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Service is Working! 502 Error Fixed!"

@app.route('/health')
def health():
    return "Healthy"

@app.route('/test')
def test():
    import os
    return f"Test OK - Port: {os.environ.get('PORT', 'not-set')}"

# For production (Gunicorn)
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting ultra-basic bot service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

