import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_environment_variables():
    """Check if all required environment variables are set"""
    load_dotenv()
    
    required_vars = [
        "GITHUB_TOKEN",
        "LINEAR_API_TOKEN", 
        "ANTHROPIC_API_KEY",
        "LINEAR_SIGNING_KEY",
        "LINEAR_TEAM_ID",
        "TARGET_REPOSITORY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file")
        return False
    
    # Check repository language
    repo_language = os.environ.get("REPOSITORY_LANGUAGE", "PYTHON").upper()
    valid_languages = ["PYTHON", "TYPESCRIPT", "JAVASCRIPT"]
    if repo_language not in valid_languages:
        logger.error(f"Invalid REPOSITORY_LANGUAGE: {repo_language}")
        logger.error(f"Valid options are: {', '.join(valid_languages)}")
        return False
    
    logger.info("All required environment variables are set")
    logger.info(f"Target repository: {os.environ.get('TARGET_REPOSITORY')}")
    logger.info(f"Repository language: {repo_language}")
    
    return True

if __name__ == "__main__":
    if not check_environment_variables():
        sys.exit(1)
    
    logger.info("Environment check passed")
    sys.exit(0) 