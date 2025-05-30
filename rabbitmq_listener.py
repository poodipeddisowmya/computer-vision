# rabbitmq_listener.py
import pika
import json
import threading
import sys
from dia import process_diameter
from extraction import process_extraction
from DB import process_inductionpad_boundingbox
import os

class RabbitMQListener:
    def __init__(self, host='10.10.3.18', port=5672, username='guest', password='guest'):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.send_queue = 'nodejs_to_python'
        self.reply_queue = 'python_to_nodejs'
        self.connection = None
        self.channel = None
        self.running = False
        
    def connect(self):
        """Establish connection to RabbitMQ."""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare queues
            self.channel.queue_declare(queue=self.send_queue, durable=False)
            self.channel.queue_declare(queue=self.reply_queue, durable=False)
            
            print(f"Connected to RabbitMQ at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to connect to RabbitMQ: {e}")
            return False
    
    def process_message(self, ch, method, properties, body):
        """Process incoming message and send response."""
        try:
            # Parse the message
            message = json.loads(body)
            print(f"Received message: {message}")
            
            filename = message.get('fileName')
            api_name = message.get('apiName')
            
            # Get the file path
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
            
            # Check if file exists
            if not os.path.exists(file_path):
                result = {"error": f"File {filename} not found in the directory"}
            else:
                # Process based on API name
                if api_name == 'object_orientation':
                    # Call diameter processing function
                    result = process_diameter(file_path)
                    
                elif api_name == 'extraction':
                    # Get extraction parameters
                    extraction_data = message.get('extractionData', {})
                    center_coords = [
                        extraction_data.get('x', 0),
                        extraction_data.get('y', 0),
                        extraction_data.get('z', 0)
                    ]
                    dimensions = [
                        extraction_data.get('dx', 1),
                        extraction_data.get('dy', 1),
                        extraction_data.get('dz', 1)
                    ]
                    
                    # Call extraction processing function
                    result = process_extraction(file_path, center_coords, dimensions)
                    
                elif api_name == 'inductionpad_boundingbox':
                    # Call inductionpad bounding box processing function
                    result = process_inductionpad_boundingbox(file_path)
                    
                else:
                    result = {"error": f"Unknown API: {api_name}"}
            
            # Send response
            response_properties = pika.BasicProperties(
                correlation_id=properties.correlation_id
            )
            
            self.channel.basic_publish(
                exchange='',
                routing_key=self.reply_queue,
                body=json.dumps(result),
                properties=response_properties
            )
            
            print(f"Sent response: {result}")
            
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"Error processing message: {e}")
            # Send error response
            error_response = {"error": str(e)}
            response_properties = pika.BasicProperties(
                correlation_id=properties.correlation_id if properties else None
            )
            
            self.channel.basic_publish(
                exchange='',
                routing_key=self.reply_queue,
                body=json.dumps(error_response),
                properties=response_properties
            )
            
            # Acknowledge the message even if there was an error
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def start_listening(self):
        """Start listening for messages."""
        if not self.connection or not self.channel:
            if not self.connect():
                return
        
        self.running = True
        print(f"Listening for messages on queue: {self.send_queue}")
        
        # Set up consumer
        self.channel.basic_consume(
            queue=self.send_queue,
            on_message_callback=self.process_message,
            auto_ack=False
        )
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"Error in consumer: {e}")
            self.stop()
    
    def stop(self):
        """Stop listening and close connections."""
        self.running = False
        if self.channel:
            try:
                self.channel.stop_consuming()
            except:
                pass
        
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
        
        print("RabbitMQ listener stopped")

def run_rabbitmq_listener(host='10.10.3.18'):
    """Run RabbitMQ listener in a separate thread."""
    listener = RabbitMQListener(host=host)
    listener_thread = threading.Thread(target=listener.start_listening)
    listener_thread.daemon = True
    listener_thread.start()
    return listener