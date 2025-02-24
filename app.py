from codegen import Codebase, CodeAgent
from codegen.extensions.clients.linear import LinearClient
from codegen.shared.enums.programming_language import ProgrammingLanguage
from codegen.extensions.tools.github.create_pr import create_pr
from helpers import create_codebase, format_linear_message, has_codegen_label, process_update_event

from fastapi import FastAPI, Request, Body, Depends
import uvicorn
import os
import logging
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Linear-Bot")

# Create a dependency for the codebase to ensure it's only created once
@lru_cache()
def get_codebase():
    logger.info("Creating codebase instance")
    repo_name = os.environ.get("TARGET_REPOSITORY")
    repo_language = os.environ.get("REPOSITORY_LANGUAGE", "PYTHON")
    
    # Convert string to ProgrammingLanguage enum
    language = ProgrammingLanguage.PYTHON
    if repo_language.upper() == "TYPESCRIPT":
        language = ProgrammingLanguage.TYPESCRIPT
    elif repo_language.upper() == "JAVASCRIPT":
        language = ProgrammingLanguage.JAVASCRIPT
    
    logger.info(f"Using repository: {repo_name} with language: {language}")
    return create_codebase(repo_name, language)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up the server")
    # Pre-load the codebase for faster responses
    get_codebase()

@app.post("/webhook")
async def handle_webhook(request: Request, data: dict = Body(...)):
    """Handle incoming webhook events from Linear"""
    logger.info(f"Received webhook: {data.get('action')} {data.get('type')}")
    
    # Check if this is an event we should handle
    if not has_codegen_label(data=data):
        logger.info("Event doesn't have Codegen label, skipping")
        return {"status": "skipped"}
    
    # Process the event
    linear_client = LinearClient(access_token=os.environ["LINEAR_API_TOKEN"])
    event = process_update_event(data)
    
    logger.info(f"Processing issue: {event.identifier} - {event.title}")
    linear_client.comment_on_issue(event.issue_id, "I'm on it 👍")

    query = format_linear_message(event.title, event.description)
    codebase = get_codebase()
    agent = CodeAgent(codebase)

    logger.info("Running agent...")
    agent.run(query)

    # Create PR
    pr_title = f"[{event.identifier}] " + event.title
    pr_body = "Codegen generated PR for issue: " + event.issue_url
    create_pr_result = create_pr(codebase, pr_title, pr_body)

    logger.info(f"PR created: {create_pr_result.url}")
    linear_client.comment_on_issue(event.issue_id, f"I've finished running, please review the PR: {create_pr_result.url}")
    
    # Reset the codebase for the next run
    codebase.reset()

    return {"status": "success"}

if __name__ == "__main__":
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")