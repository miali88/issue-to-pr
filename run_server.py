import subprocess
import threading
import time
import logging
import os
import sys
import requests
import json
from dotenv import load_dotenv
from check_env import check_environment_variables

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def register_linear_webhook(webhook_url):
    """Register the webhook URL with Linear using their GraphQL API"""
    logger.info("Attempting to register webhook with Linear...")
    
    # Get Linear API token from environment
    linear_api_token = os.environ.get("LINEAR_API_TOKEN")
    if not linear_api_token:
        logger.error("LINEAR_API_TOKEN not found in environment variables")
        return False
    
    # Get Linear team ID from environment
    linear_team_id = os.environ.get("LINEAR_TEAM_ID")
    if not linear_team_id:
        logger.error("LINEAR_TEAM_ID not found in environment variables")
        return False
    
    # GraphQL endpoint
    url = "https://api.linear.app/graphql"
    
    # Headers for authentication
    headers = {
        "Authorization": f"{linear_api_token}",
        "Content-Type": "application/json"
    }
    
    # First, check if a webhook with this URL already exists
    query = """
    query Webhooks {
        webhooks {
            nodes {
                id
                url
                label
            }
        }
    }
    """
    
    try:
        response = requests.post(url, json={"query": query}, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        webhooks = data.get("data", {}).get("webhooks", {}).get("nodes", [])
        
        # Check if webhook already exists
        existing_webhook = None
        for webhook in webhooks:
            if webhook.get("url") == webhook_url:
                existing_webhook = webhook
                break
        
        if existing_webhook:
            logger.info(f"Webhook already exists with ID: {existing_webhook.get('id')}")
            return True
        
        # If webhook doesn't exist, create it
        mutation = """
        mutation CreateWebhook($url: String!, $label: String!, $teamId: String!) {
            webhookCreate(input: {
                url: $url
                label: $label
                teamId: $teamId
                resourceTypes: [Issue]
                enabled: true
            }) {
                success
                webhook {
                    id
                    url
                    label
                }
            }
        }
        """
        
        variables = {
            "url": webhook_url,
            "label": "Codegen Bot Webhook",
            "teamId": linear_team_id
        }
        
        response = requests.post(
            url, 
            json={"query": mutation, "variables": variables}, 
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        success = data.get("data", {}).get("webhookCreate", {}).get("success", False)
        
        if success:
            webhook_id = data.get("data", {}).get("webhookCreate", {}).get("webhook", {}).get("id")
            logger.info(f"Successfully registered webhook with Linear. Webhook ID: {webhook_id}")
            return True
        else:
            errors = data.get("errors", [])
            logger.error(f"Failed to register webhook with Linear: {errors}")
            # Log the full response for debugging
            logger.error(f"Full response: {json.dumps(data, indent=2)}")
            return False
            
    except Exception as e:
        logger.error(f"Error registering webhook with Linear: {str(e)}")
        # Log more details about the error for debugging
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response details: {e.response.text}")
        return False

def run_fastapi_server():
    """Run the FastAPI server in a subprocess"""
    logger.info("Starting FastAPI server...")
    server_process = subprocess.Popen(
        ["python", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Log the FastAPI server output
    def log_output(stream):
        for line in stream:
            # Treat all output as INFO level
            logger.info(line.strip())
    
    threading.Thread(target=log_output, args=(server_process.stdout,), daemon=True).start()
    threading.Thread(target=log_output, args=(server_process.stderr,), daemon=True).start()
    
    return server_process

def run_ngrok():
    """Run Ngrok in a subprocess and extract the webhook URL
    
    Returns:
        tuple: (ngrok_process, webhook_url)
    """
    logger.info("Starting Ngrok tunnel with static subdomain 'internally-wise-spaniel'...")
    
    # Use subprocess to capture the output
    ngrok_process = subprocess.Popen(
        ["python", "ngrok.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Variable to store the webhook URL
    webhook_url = None
    
    # Log the Ngrok output with filtering and extract webhook URL
    def log_ngrok_output(stream):
        nonlocal webhook_url
        for line in stream:
            line = line.strip()
            # Only log the important URL information and errors
            if "NGROK TUNNEL ESTABLISHED:" in line or "WEBHOOK URL:" in line or "=" * 10 in line or "ERROR" in line:
                logger.info(line)
                
                # Extract webhook URL if present
                if "WEBHOOK URL:" in line:
                    webhook_url = line.split("WEBHOOK URL:")[1].strip()
    
    # Start threads to process output
    stdout_thread = threading.Thread(target=log_ngrok_output, args=(ngrok_process.stdout,), daemon=True)
    stderr_thread = threading.Thread(target=log_ngrok_output, args=(ngrok_process.stderr,), daemon=True)
    
    stdout_thread.start()
    stderr_thread.start()
    
    # Wait a bit for ngrok to start and for the webhook URL to be extracted
    max_wait = 15  # seconds (increased from 10)
    wait_interval = 0.5  # seconds
    for _ in range(int(max_wait / wait_interval)):
        if webhook_url:
            break
        time.sleep(wait_interval)
    
    if webhook_url:
        logger.info(f"Successfully extracted webhook URL: {webhook_url}")
        logger.info(f"This URL will be consistent across restarts due to the static subdomain")
    else:
        logger.warning("Could not extract webhook URL from ngrok output")
        logger.warning("There might be an issue with the ngrok service or the subdomain might be in use")
        logger.warning("Check if the subdomain 'internally-wise-spaniel' is available or try a different one")
    
    return ngrok_process, webhook_url

def main():
    """Main function to start both the server and ngrok"""
    logger.info("Starting services...")
    
    # Check environment variables
    if not check_environment_variables():
        logger.error("Environment check failed. Please fix the issues and try again.")
        sys.exit(1)
    
    logger.info("Environment check passed, starting services...")
    
    # Start the FastAPI server
    server_process = run_fastapi_server()
    
    # Wait for server to start
    time.sleep(3)
    
    # Start Ngrok and get the webhook URL
    ngrok_process, webhook_url = run_ngrok()
    
    # Register the webhook with Linear
    if webhook_url:
        logger.info("=" * 60)
        logger.info("Attempting to register webhook with Linear...")
        if register_linear_webhook(webhook_url):
            logger.info("✅ Webhook registration successful!")
            logger.info("Your Linear webhook is now configured to send events to this application.")
        else:
            logger.error("❌ Webhook registration failed.")
            logger.error("You will need to manually configure the webhook in Linear settings.")
        logger.info("=" * 60)
    else:
        logger.warning("No webhook URL extracted from Ngrok output.")
        logger.warning("You will need to manually configure the webhook in Linear settings.")
    
    logger.info("All services started. Press Ctrl+C to stop.")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt. Shutting down...")
        server_process.terminate()
        ngrok_process.terminate()
        
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    main() 