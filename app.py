from codegen import Codebase, CodeAgent
from codegen.extensions.clients.linear import LinearClient
from codegen.shared.enums.programming_language import ProgrammingLanguage
from codegen.extensions.tools.github.create_pr import create_pr
from helpers import create_codebase, format_linear_message, has_codegen_label, process_update_event, get_linear_issue_id, manually_create_pr, manually_clone_repository

from fastapi import FastAPI, Request, Body, Depends
import uvicorn
import os
import logging
from functools import lru_cache
from dotenv import load_dotenv
import tempfile
import subprocess
import requests
import json

# Load environment variables from .env file
load_dotenv()

# Get GitHub token from environment variables
github_token = os.environ.get("GITHUB_TOKEN")
if not github_token:
    logger.warning("GITHUB_TOKEN not found in environment variables")

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
    
    # Debug: Print the token being used (first few chars only)
    if github_token:
        print("TOKENNENEN", github_token)
        token_preview = github_token[:10] + "..." if len(github_token) > 10 else "too_short"
        logger.info(f"Using GitHub token starting with: {token_preview}")
    else:
        logger.error("GitHub token is not set in environment variables")
    
    # Verify GitHub token
    try:
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"GitHub token is valid. Authenticated as: {user_data.get('login')}")
            
            # Check repo access
            repo_name = os.environ.get("TARGET_REPOSITORY")
            if repo_name:
                repo_response = requests.get(f"https://api.github.com/repos/{repo_name}", headers=headers)
                if repo_response.status_code == 200:
                    repo_data = repo_response.json()
                    logger.info(f"GitHub token has access to repository: {repo_name}")
                    logger.info(f"Repository permissions: {repo_data.get('permissions', {})}")
                else:
                    logger.error(f"GitHub token does not have access to repository {repo_name}. Status code: {repo_response.status_code}")
                    logger.error(f"Response: {repo_response.text}")
        else:
            logger.error(f"GitHub token is invalid. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
    except Exception as e:
        logger.error(f"Error verifying GitHub token: {str(e)}")
    
    # Verify Linear API token
    linear_api_token = os.environ.get("LINEAR_API_TOKEN") or os.environ.get("LINEAR_API_KEY")
    if linear_api_token:
        token_preview = linear_api_token[:5] + "..." if len(linear_api_token) > 5 else "too_short"
        logger.info(f"Using Linear API token starting with: {token_preview}")
        
        try:
            # Try to verify the Linear API token by making a simple request
            headers = {
                "Authorization": linear_api_token,
                "Content-Type": "application/json"
            }
            # GraphQL query to get the authenticated user
            query = """
            query {
                viewer {
                    id
                    name
                    email
                }
            }
            """
            response = requests.post(
                "https://api.linear.app/graphql",
                headers=headers,
                json={"query": query}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    logger.error(f"Linear API token is invalid: {data['errors']}")
                else:
                    viewer = data.get("data", {}).get("viewer", {})
                    logger.info(f"Linear API token is valid. Authenticated as: {viewer.get('name')} ({viewer.get('email')})")
            else:
                logger.error(f"Linear API token verification failed. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"Error verifying Linear API token: {str(e)}")
    else:
        logger.error("Linear API token is not set in environment variables")

@app.post("/webhook")
async def handle_webhook(request: Request, data: dict = Body(...)):
    """Handle incoming webhook events from Linear"""
    logger.info(f"Received webhook: {data.get('action')} {data.get('type')}")
    logger.info(f"Webhook payload: {data}")
    
    try:
        # Check if this is an event we should handle
        if not has_codegen_label(data=data):
            logger.info("Event doesn't have Codegen label, skipping")
            return {"status": "skipped"}
        
        # Process the event
        linear_api_token = os.environ.get("LINEAR_API_TOKEN") or os.environ.get("LINEAR_API_KEY")
        if not linear_api_token:
            logger.error("No Linear API token found in environment variables")
            return {"status": "error", "message": "No Linear API token found"}
        
        # Ensure the token has the correct format (should start with 'lin_api_')
        if not linear_api_token.startswith("lin_api_"):
            logger.warning(f"Linear API token doesn't have the expected format (should start with 'lin_api_')")
            
        linear_client = LinearClient(access_token=linear_api_token)
        event = process_update_event(data)
        
        logger.info(f"Processing issue: {event.identifier} - {event.title}")
        logger.info(f"Issue ID: {event.issue_id}")
        logger.info(f"Issue Identifier: {event.identifier}")
        
        # Get the correct issue ID format for Linear API
        linear_issue_id = get_linear_issue_id(event.issue_id, event.identifier)
        logger.info(f"Using Linear issue ID: {linear_issue_id}")
        
        # Debug Linear API token
        token_preview = linear_api_token[:5] + "..." if linear_api_token and len(linear_api_token) > 5 else "not set"
        logger.info(f"Using Linear API token starting with: {token_preview}")
        
        try:
            logger.info(f"Attempting to comment on Linear issue: {linear_issue_id}")
            linear_client.comment_on_issue(linear_issue_id, "I'm on it 👍")
            logger.info("Successfully commented on Linear issue")
        except Exception as e:
            logger.error(f"Error commenting on issue: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            # Continue processing even if commenting fails
        
        # Get the codebase
        codebase = get_codebase()
        
        # Get the repository directory from the codebase object
        repo_dir = None
        if hasattr(codebase, '_repo_dir'):
            repo_dir = codebase._repo_dir
        elif hasattr(codebase, 'repo_dir'):
            repo_dir = codebase.repo_dir
        elif hasattr(codebase, 'repository_dir'):
            repo_dir = codebase.repository_dir
        elif hasattr(codebase, 'repo_path'):
            repo_dir = codebase.repo_path
        elif hasattr(codebase, 'path'):
            repo_dir = codebase.path
        elif hasattr(codebase, 'get_repo_dir') and callable(codebase.get_repo_dir):
            repo_dir = codebase.get_repo_dir()
        elif hasattr(codebase, 'get_path') and callable(codebase.get_path):
            repo_dir = codebase.get_path()
        
        # If we still don't have a repository directory, try to find it in the temporary directory
        if not repo_dir:
            tmp_dir = tempfile.gettempdir()
            repo_name = os.environ.get("TARGET_REPOSITORY")
            if repo_name:
                possible_repo_dir = os.path.join(tmp_dir, repo_name.split('/')[-1])
                if os.path.exists(possible_repo_dir):
                    logger.info(f"Found repository directory in tmp_dir: {possible_repo_dir}")
                    repo_dir = possible_repo_dir
                else:
                    logger.info("Attempting to manually clone the repository")
                    repo_dir = manually_clone_repository(repo_name)
        
        if not repo_dir:
            logger.error("Could not find repository directory in codebase object")
            return {"status": "error", "message": "Could not find repository directory"}
        
        # Create a branch for the issue before making any changes
        branch_name = f"codegen/{event.identifier.lower().replace('-', '_')}"
        logger.info(f"Creating branch: {branch_name}")
        
        try:
            # Make sure we're on the main branch first
            subprocess.check_call(["git", "checkout", "main"], cwd=repo_dir)
            # Pull latest changes
            subprocess.check_call(["git", "pull"], cwd=repo_dir)
            # Create and checkout a new branch
            subprocess.check_call(["git", "checkout", "-b", branch_name], cwd=repo_dir)
            logger.info(f"Successfully created and checked out branch: {branch_name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creating branch: {str(e)}")
            # If the branch already exists, try to use it
            try:
                subprocess.check_call(["git", "checkout", branch_name], cwd=repo_dir)
                logger.info(f"Branch already exists, checked out existing branch: {branch_name}")
            except subprocess.CalledProcessError as checkout_error:
                logger.error(f"Error checking out existing branch: {str(checkout_error)}")
                return {"status": "error", "message": f"Failed to create or checkout branch: {str(e)}"}
        
        # Now run the agent on the new branch
        query = format_linear_message(event.title, event.description)
        agent = CodeAgent(codebase)
        
        logger.info("Running agent...")
        agent.run(query)
        
        # Check if any changes were made by the agent
        try:
            git_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_dir).decode('utf-8').strip()
            if not git_status:
                logger.warning("No changes detected in the repository. The agent didn't make any modifications.")
                try:
                    linear_client.comment_on_issue(linear_issue_id, "I analyzed the issue but didn't make any changes to the codebase. No PR was created.")
                except Exception as e:
                    logger.error(f"Error commenting on issue: {str(e)}")
                
                # Reset the codebase for the next run
                logger.info("Resetting codebase and returning early due to no changes")
                codebase.reset()
                return {"status": "success", "message": "No changes made"}
            
            logger.info(f"Changes detected in the repository: {git_status}")
            
            # Create PR only if changes were made
            pr_title = f"[{event.identifier}] " + event.title
            pr_body = "Codegen generated PR for issue: " + event.issue_url
            
            try:
                # First try to use the SDK's create_pr function
                logger.info("Attempting to create PR using SDK")
                create_pr_result = create_pr(codebase, pr_title, pr_body)
                
                if hasattr(create_pr_result, 'url') and create_pr_result.url:
                    logger.info(f"PR created successfully: {create_pr_result.url}")
                    
                    try:
                        linear_client.comment_on_issue(linear_issue_id, f"I've finished running, please review the PR: {create_pr_result.url}")
                    except Exception as e:
                        logger.error(f"Error commenting on issue with PR link: {str(e)}")
                else:
                    logger.error(f"PR creation failed: PR result object doesn't have a valid URL. Result: {create_pr_result}")
                    
                    # Try manual PR creation as fallback
                    logger.info("Attempting manual PR creation as fallback")
                    manual_pr_result = manually_create_pr(repo_dir, branch_name, pr_title, pr_body)
                    
                    if manual_pr_result.get("url"):
                        logger.info(f"Manual PR created successfully: {manual_pr_result['url']}")
                        try:
                            linear_client.comment_on_issue(linear_issue_id, f"I've finished running, please review the PR: {manual_pr_result['url']}")
                        except Exception as e:
                            logger.error(f"Error commenting on issue with manual PR link: {str(e)}")
                    else:
                        logger.error(f"Manual PR creation failed: {manual_pr_result.get('error')}")
                        try:
                            linear_client.comment_on_issue(linear_issue_id, f"I encountered an error while creating the PR: {manual_pr_result.get('error')}")
                        except Exception as comment_error:
                            logger.error(f"Error commenting on issue with manual PR error: {str(comment_error)}")
            except Exception as e:
                logger.error(f"Error creating PR: {str(e)}")
                logger.error(f"Full error details: {e}")
                
                # Try manual PR creation as fallback
                logger.info("Attempting manual PR creation as fallback after exception")
                manual_pr_result = manually_create_pr(repo_dir, branch_name, pr_title, pr_body)
                
                if manual_pr_result.get("url"):
                    logger.info(f"Manual PR created successfully: {manual_pr_result['url']}")
                    try:
                        linear_client.comment_on_issue(linear_issue_id, f"I've finished running, please review the PR: {manual_pr_result['url']}")
                    except Exception as e:
                        logger.error(f"Error commenting on issue with manual PR link: {str(e)}")
                else:
                    logger.error(f"Manual PR creation failed: {manual_pr_result.get('error')}")
                    try:
                        linear_client.comment_on_issue(linear_issue_id, f"I encountered an error while creating the PR: {manual_pr_result.get('error')}")
                    except Exception as comment_error:
                        logger.error(f"Error commenting on issue with PR error: {str(comment_error)}")
        except Exception as e:
            logger.error(f"Error checking git status or creating PR: {str(e)}")
            logger.error(f"Full error details: {e}")
        
        # Reset the codebase for the next run
        codebase.reset()

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")