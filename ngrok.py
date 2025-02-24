import logging
import os
from pyngrok import ngrok, conf
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_ngrok_tunnel():
    """Start the Ngrok tunnel with proper error handling
    
    Returns:
        str: The webhook URL if successful, None otherwise
    """
    logger.info('Starting ngrok tunnel setup')
    
    try:
        # Define port - this should match the port in app.py
        port = 8000
        
        # Get subdomain from environment variable or use default
        subdomain = os.environ.get("NGROK_SUBDOMAIN")
        
        # Configure tunnel options
        options = {"addr": f"http://localhost:{port}"}
        if subdomain:
            options["subdomain"] = subdomain
            logger.info(f"Using custom subdomain: {subdomain}")
        else:
            logger.info("Using random subdomain (set NGROK_SUBDOMAIN env var for a custom one)")
        
        # Start the tunnel
        http_tunnel = ngrok.connect(**options)
        
        webhook_url = f"{http_tunnel.public_url}/webhook"
        
        # Make the important URLs stand out
        logger.info("=" * 60)
        logger.info(f"NGROK TUNNEL ESTABLISHED: {http_tunnel.public_url}")
        logger.info(f"WEBHOOK URL: {webhook_url}")
        logger.info("IMPORTANT: Configure this webhook URL in Linear to receive events")
        logger.info("=" * 60)
        
        # Keep the script running until interrupted
        ngrok_process = ngrok.get_ngrok_process()
        
        # Return the webhook URL for registration
        return webhook_url, ngrok_process
            
    except Exception as e:
        logger.error(f"An error occurred with ngrok: {str(e)}")
        ngrok.kill()  # Ensure ngrok is killed if an error occurs
        raise
        
    return None, None

if __name__ == "__main__":
    webhook_url, ngrok_process = start_ngrok_tunnel()
    
    if webhook_url and ngrok_process:
        try:
            # Block until CTRL-C
            ngrok_process.proc.wait()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt. Closing tunnels...")
        finally:
            ngrok.kill()  # Kill the ngrok process on exit
            logger.info("Tunnels closed")
