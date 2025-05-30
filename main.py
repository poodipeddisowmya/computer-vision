# simplified_app.py
from flask import Flask, request, jsonify
import os
import signal
import sys

# Import functions from dia.py and extraction.py
from dia import process_diameter
from extraction import process_extraction

# Import RabbitMQ listener
from rabbitmq_listener import run_rabbitmq_listener

app = Flask(__name__)
rabbitmq_listener = None

@app.route('/dia', methods=['POST'])
def diameter_api():
    """API endpoint for computing diameter between selected points."""
    if 'filename' not in request.form:
        return jsonify({"error": "No filename provided"}), 400
    
    filename = request.form.get('filename')
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": f"File {filename} not found in the directory"}), 404
    
    try:
        # Process the PCD file for diameter calculation
        result = process_diameter(file_path)
        
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/extraction', methods=['POST'])
def extraction_api():
    """API endpoint for extracting ROI from a point cloud."""
    if 'filename' not in request.form:
        return jsonify({"error": "No filename provided"}), 400
    
    # Get parameters
    try:
        x = float(request.form.get('x', 0))
        y = float(request.form.get('y', 0))
        z = float(request.form.get('z', 0))
        dx = float(request.form.get('dx', 1))
        dy = float(request.form.get('dy', 1))
        dz = float(request.form.get('dz', 1))
    except ValueError:
        return jsonify({"error": "Invalid ROI parameters"}), 400
    
    filename = request.form.get('filename')
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": f"File {filename} not found in the directory"}), 404
    
    try:
        # Process the PCD file for ROI extraction and measurement
        center_coords = [x, y, z]
        dimensions = [dx, dy, dz]
        result = process_extraction(file_path, center_coords, dimensions)
        
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def cleanup():
    """Cleanup function to properly stop RabbitMQ listener."""
    global rabbitmq_listener
    if rabbitmq_listener:
        print("Shutting down RabbitMQ listener...")
        rabbitmq_listener.stop()

def signal_handler(sig, frame):
    """Handle shutdown signal."""
    print("Shutdown signal received")
    cleanup()
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start RabbitMQ listener
    rabbitmq_host = '10.10.3.18'  # Change this to your RabbitMQ host if different
    print(f"Starting RabbitMQ listener on {rabbitmq_host}...")
    rabbitmq_listener = run_rabbitmq_listener(host=rabbitmq_host)
    
    try:
        # Run the Flask app
        print("Starting Flask server on http://127.0.0.1:5000/")
        app.run(host='127.0.0.1', port=5000, debug=False)
    finally:
        cleanup()