from codegen import Codebase, ProgrammingLanguage
from typing import List, Dict, Any, Optional, Callable
from codegen.sdk.codebase.config import CodebaseConfig
from data import LinearLabels, LinearIssueUpdateEvent
import os
import logging
import tempfile
import subprocess
import requests
import json
import time


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_agent_progress(message: str, linear_client=None, issue_id: Optional[str] = None):
    """
    Log the agent's progress and optionally comment on the Linear issue.
    
    Args:
        message: The message to log.
        linear_client: The Linear client to use for commenting on the issue.
        issue_id: The ID of the Linear issue to comment on.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    
    # Log to the console
    logger.info(log_message)
    
    # Comment on the Linear issue if a client and issue ID are provided
    if linear_client and issue_id:
        try:
            linear_client.comment_on_issue(issue_id, message)
            logger.info(f"Commented on Linear issue {issue_id}")
        except Exception as e:
            logger.error(f"Error commenting on Linear issue: {str(e)}")


def process_update_event(event_data: dict[str, Any]):
    print("processing update event")
    logging.info(f"Processing event data: {event_data}")

    action = event_data.get("action")
    actor = event_data.get("actor")
    created_at = event_data.get("createdAt")
    issue_url = event_data.get("url")
    data: Dict[str, Any] = event_data.get("data", {})
    
    # Extract the issue ID correctly - Linear API expects the full ID, not just the numeric part
    issue_id = data.get("id")
    logging.info(f"Extracted issue_id: {issue_id}")
    
    title = data.get("title")
    description = data.get("description")
    identifier = data.get("identifier")

    labels: List[LinearLabels] = data.get("labels", [])
    updated_from: Dict[str, Any] = event_data.get("updatedFrom", {})

    update_event = LinearIssueUpdateEvent(
        issue_id=issue_id,
        action=action,
        actor=actor,
        created_at=created_at,
        issue_url=issue_url,
        data=data,
        labels=labels,
        updated_from=updated_from,
        title=title,
        description=description,
        identifier=identifier,
    )
    return update_event


def format_linear_message(title: str, description: str | None = "") -> str:
    """Format a Linear update event into a message for the agent"""

    return f"""
    Here is a new issue titled '{title}' and with the description '{description}'. 
    
    Your task is to:
    1. Understand the requirements in the issue
    2. Research any necessary documentation or information using web search when needed
    3. Review the relevant parts of the codebase to understand the existing implementation
    4. Make necessary code changes to implement the requirements
    5. Create a pull request with your changes
    
    IMPORTANT: You MUST make changes to the codebase to implement the requirements. Do not just analyze without making changes.
    
    Use your tools to query the codebase for more context. When applicable include references to files and line numbers.
    If you need to research documentation, APIs, or best practices, use the web search tool to find relevant information.
    
    For each step of your implementation:
    1. Log your thought process and decisions
    2. Use web search when you need to find documentation or examples
    3. Explain your changes with code snippets and references
    
    Make sure to create a pull request with your changes when you're done.
    """


def has_codegen_label(*args, **kwargs):
    body = kwargs.get("data")
    type = body.get("type")
    action = body.get("action")

    if type == "Issue" and action == "update":
        # handle issue update (label updates)
        try:
            update_event = process_update_event(body)
            
            # Check if labels exist
            if not update_event.labels:
                logger.info("No labels found in the event, skipping codegen bot response")
                return False
                
            has_codegen_label = any(label.name == "Codegen" for label in update_event.labels)
            
            # Find the Codegen label ID if it exists
            codegen_label_id = next((label.id for label in update_event.labels if label.name == "Codegen"), None)
            
            # Check if the updated_from field has the expected structure
            if not update_event.updated_from:
                logger.info("No updated_from field found in the event")
                # If Codegen label is present but we can't determine if it was just added,
                # we'll assume it was just added
                return has_codegen_label
                
            # Check if the label was previously present
            previous_labels = update_event.updated_from.get("labelIds", [])
            had_codegen_label = codegen_label_id in previous_labels if codegen_label_id else False
            
            if previous_labels is None or not has_codegen_label:
                logger.info("No labels updated or no Codegen label present, skipping codegen bot response")
                return False

            if has_codegen_label and not had_codegen_label:
                logger.info("Codegen label added, codegen bot will respond")
                return True

            logger.info("Codegen label removed or already existed, codegen bot will not respond")
            return False
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {str(e)}")
            return False
    
    logger.info(f"Event type {type} with action {action} not supported, skipping")
    return False


def create_codebase(repo_name: str, language: ProgrammingLanguage):
    config = CodebaseConfig()
    github_token = os.getenv("GITHUB_TOKEN")
    # Debug: Print the full token to verify it's correct
    print(f"DEBUG - Full GitHub token: {github_token}")
    token_preview = github_token[:10] + "..." if len(github_token) > 10 else "too_short"
    logger.info(f"Using GitHub token starting with: {token_preview} in create_codebase")
    config.secrets.github_token = github_token
    
    # Use a temporary directory in the user's home directory instead of /root
    tmp_dir = tempfile.gettempdir()
    
    logger.info(f"Using temporary directory: {tmp_dir}")
    codebase = Codebase.from_repo(repo_name, language=language, tmp_dir=tmp_dir, config=config)
    
    # Debug: Log information about the codebase object
    logger.info(f"Codebase object type: {type(codebase)}")
    logger.info(f"Codebase object attributes: {dir(codebase)}")
    
    # Try to find the repository directory
    repo_dir = None
    if hasattr(codebase, 'repo_dir'):
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
    
    if repo_dir:
        logger.info(f"Found repository directory: {repo_dir}")
        # Store the repository directory as a custom attribute
        codebase._repo_dir = repo_dir
    else:
        logger.warning("Could not find repository directory in codebase object")
        # Try to find the repository directory in the temporary directory
        possible_repo_dir = os.path.join(tmp_dir, repo_name.split('/')[-1])
        if os.path.exists(possible_repo_dir):
            logger.info(f"Found repository directory in tmp_dir: {possible_repo_dir}")
            codebase._repo_dir = possible_repo_dir
        else:
            logger.error(f"Repository directory not found in tmp_dir: {possible_repo_dir}")
    
    return codebase


def get_linear_issue_id(issue_id: str, identifier: str = None):
    """
    Get the correct issue ID format for Linear API.
    Linear API might expect different formats for different operations.
    
    Args:
        issue_id: The raw issue ID from the webhook payload
        identifier: The issue identifier (e.g., DEV-78)
        
    Returns:
        The correctly formatted issue ID for Linear API
    """
    logger = logging.getLogger(__name__)
    
    # If identifier is provided, use it as it's more reliable for API operations
    if identifier:
        logger.info(f"Using identifier for Linear API: {identifier}")
        return identifier
    
    # Otherwise, use the raw issue ID
    logger.info(f"Using raw issue ID for Linear API: {issue_id}")
    return issue_id


def manually_create_pr(repo_dir: str, branch_name: str, pr_title: str, pr_body: str) -> Dict[str, Any]:
    """
    Manually create a PR using git commands and GitHub API if the automatic process fails.
    
    Args:
        repo_dir: Path to the repository directory
        branch_name: Name of the branch to create
        pr_title: Title of the PR
        pr_body: Body of the PR
        
    Returns:
        Dict with PR information including URL
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Attempting to manually create PR from directory: {repo_dir}")
    
    try:
        # Verify the repository directory exists
        if not repo_dir or not os.path.exists(repo_dir):
            logger.error(f"Repository directory does not exist: {repo_dir}")
            
            # Try to find the repository directory in the temporary directory
            tmp_dir = tempfile.gettempdir()
            repo_name = os.environ.get("TARGET_REPOSITORY")
            if repo_name:
                possible_repo_dir = os.path.join(tmp_dir, repo_name.split('/')[-1])
                if os.path.exists(possible_repo_dir):
                    logger.info(f"Found repository directory in tmp_dir: {possible_repo_dir}")
                    repo_dir = possible_repo_dir
                else:
                    logger.error(f"Repository directory not found in tmp_dir: {possible_repo_dir}")
                    logger.info("Attempting to manually clone the repository")
                    repo_dir = manually_clone_repository(repo_name)
                    if not repo_dir:
                        return {"error": "Failed to clone repository", "url": None}
            else:
                return {"error": "Repository directory not found and TARGET_REPOSITORY not set", "url": None}
        
        # Verify the repository is initialized with git
        git_dir = os.path.join(repo_dir, '.git')
        if not os.path.exists(git_dir):
            logger.error(f"Repository is not initialized with git (no .git directory): {repo_dir}")
            
            # Try to manually clone the repository
            repo_name = os.environ.get("TARGET_REPOSITORY")
            if repo_name:
                logger.info("Attempting to manually clone the repository")
                repo_dir = manually_clone_repository(repo_name)
                if not repo_dir:
                    return {"error": "Failed to clone repository", "url": None}
            else:
                return {"error": "Repository is not initialized with git and TARGET_REPOSITORY not set", "url": None}
        
        # Get the GitHub token
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            logger.error("GitHub token not found in environment variables")
            return {"error": "GitHub token not found"}
            
        # Get the repository name
        repo_name = os.environ.get("TARGET_REPOSITORY")
        if not repo_name:
            logger.error("TARGET_REPOSITORY not found in environment variables")
            return {"error": "Repository name not found"}
            
        # Check if there are any changes
        status_output = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_dir).decode('utf-8').strip()
        if not status_output:
            logger.warning("No changes detected in the repository")
            return {"error": "No changes to commit", "url": None}
            
        # Check if we're already on the correct branch
        current_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir).decode('utf-8').strip()
        logger.info(f"Current branch: {current_branch}")
        
        if current_branch != branch_name:
            # Check if the branch already exists
            try:
                # List all branches
                branches = subprocess.check_output(["git", "branch"], cwd=repo_dir).decode('utf-8').strip()
                branch_exists = branch_name in branches
                
                if branch_exists:
                    logger.info(f"Branch {branch_name} already exists, checking it out")
                    subprocess.check_call(["git", "checkout", branch_name], cwd=repo_dir)
                else:
                    # Create a new branch
                    logger.info(f"Creating branch: {branch_name}")
                    subprocess.check_call(["git", "checkout", "-b", branch_name], cwd=repo_dir)
            except subprocess.CalledProcessError as e:
                logger.error(f"Error managing branch: {str(e)}")
                # Try to create the branch anyway
                try:
                    subprocess.check_call(["git", "checkout", "-b", branch_name], cwd=repo_dir)
                except subprocess.CalledProcessError as branch_error:
                    logger.error(f"Failed to create branch: {str(branch_error)}")
                    return {"error": f"Failed to create branch: {str(branch_error)}", "url": None}
        
        # Add all changes
        logger.info("Adding all changes")
        subprocess.check_call(["git", "add", "."], cwd=repo_dir)
        
        # Commit changes
        logger.info("Committing changes")
        subprocess.check_call(["git", "commit", "-m", pr_title], cwd=repo_dir)
        
        # Push to GitHub
        logger.info(f"Pushing branch {branch_name} to GitHub")
        push_command = ["git", "push", "-u", "origin", branch_name]
        
        # Set up the environment with the GitHub token for authentication
        env = os.environ.copy()
        # Format: https://{username}:{token}@github.com
        remote_url = f"https://x-access-token:{github_token}@github.com/{repo_name}.git"
        
        # Set the remote URL with the token
        subprocess.check_call(["git", "remote", "set-url", "origin", remote_url], cwd=repo_dir)
        
        # Push to GitHub
        subprocess.check_call(push_command, cwd=repo_dir)
        
        # Create PR using GitHub API
        logger.info("Creating PR using GitHub API")
        [owner, repo] = repo_name.split('/')
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": "main"  # Assuming the base branch is main
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        pr_data = response.json()
        pr_url = pr_data.get("html_url")
        logger.info(f"PR created successfully: {pr_url}")
        
        return {"url": pr_url, "data": pr_data}
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {e.cmd}. Return code: {e.returncode}")
        if hasattr(e, 'output') and e.output:
            logger.error(f"Command output: {e.output.decode('utf-8')}")
        return {"error": f"Git command failed: {e.cmd}", "url": None}
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API request failed: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response text: {e.response.text}")
        return {"error": f"GitHub API request failed: {str(e)}", "url": None}
    except Exception as e:
        logger.error(f"Error creating PR manually: {str(e)}")
        return {"error": str(e), "url": None}


def manually_clone_repository(repo_name: str, target_dir: str = None) -> str:
    """
    Manually clone a repository using git commands.
    
    Args:
        repo_name: Name of the repository (username/repo)
        target_dir: Target directory to clone into (optional)
        
    Returns:
        Path to the cloned repository directory
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Manually cloning repository: {repo_name}")
    
    try:
        # Get the GitHub token
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            logger.error("GitHub token not found in environment variables")
            return None
        
        # Use the temporary directory if target_dir is not provided
        if not target_dir:
            target_dir = tempfile.gettempdir()
        
        # Create the target directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)
        
        # Format the repository URL with the token
        repo_url = f"https://x-access-token:{github_token}@github.com/{repo_name}.git"
        
        # Get the repository name without the username
        repo_name_only = repo_name.split('/')[-1]
        
        # Full path to the cloned repository
        repo_dir = os.path.join(target_dir, repo_name_only)
        
        # Check if the repository already exists
        if os.path.exists(repo_dir):
            logger.info(f"Repository already exists at {repo_dir}, pulling latest changes")
            # Pull the latest changes
            subprocess.check_call(["git", "pull"], cwd=repo_dir)
            return repo_dir
        
        # Clone the repository
        logger.info(f"Cloning repository to {repo_dir}")
        subprocess.check_call(["git", "clone", repo_url, repo_dir])
        
        # Verify the repository was cloned successfully
        if os.path.exists(os.path.join(repo_dir, '.git')):
            logger.info(f"Repository cloned successfully to {repo_dir}")
            return repo_dir
        else:
            logger.error(f"Failed to clone repository to {repo_dir}")
            return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {e.cmd}. Return code: {e.returncode}")
        if hasattr(e, 'output') and e.output:
            logger.error(f"Command output: {e.output.decode('utf-8')}")
        return None
    except Exception as e:
        logger.error(f"Error cloning repository: {str(e)}")
        return None