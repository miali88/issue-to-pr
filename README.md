# Linear Ticket to GitHub PR Bot

This project demonstrates how to deploy an agentic bot that automatically creates GitHub Pull Requests from Linear tickets. The bot leverages Linear's webhook system to listen for ticket updates and uses AI to generate corresponding GitHub PRs with appropriate code changes.

## Features

- Automatically processes Linear tickets with the "Codegen" label
- Uses AI to analyze the codebase and implement requested changes
- Creates GitHub Pull Requests with the implemented changes
- Provides internet search capabilities to research documentation and best practices
- Comments on Linear tickets with progress updates and PR links

### Enhanced AI Capabilities

The bot includes several custom tools to enhance its capabilities:

1. **WebSearchTool**: Built-in tool for basic internet search
2. **CustomWebSearchTool**: Enhanced search tool that provides more detailed results
3. **CustomDocumentationTool**: Specialized tool for fetching library and API documentation

These tools allow the AI to:
- Research necessary documentation when implementing features
- Look up best practices and coding patterns
- Find examples and reference implementations
- Stay up-to-date with the latest APIs and libraries

## Prerequisites

Before running this application, you'll need the following API tokens and credentials:

- GitHub API Token
- Linear API Token
- Anthropic API Token (required for internet search capabilities)
- Linear Signing Key
- Linear Team ID
- Ngrok auth token (sign up at [ngrok.com](https://ngrok.com))

## Setup

1. Clone the repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your environment variables in a `.env` file:
   ```env
   GITHUB_TOKEN=your_github_token
   LINEAR_API_TOKEN=your_linear_token
   ANTHROPIC_API_KEY=your_anthropic_token  # Required for internet search capabilities
   LINEAR_SIGNING_KEY=your_linear_signing_key
   LINEAR_TEAM_ID=your_team_id
   NGROK_AUTH_TOKEN=your_ngrok_auth_token
   
   # Target repository configuration
   TARGET_REPOSITORY=your-username/your-project-repo
   REPOSITORY_LANGUAGE=TYPESCRIPT  # Options: PYTHON, TYPESCRIPT, JAVASCRIPT
   ```

4. Configure Ngrok:
   ```bash
   ngrok authtoken your_ngrok_auth_token
   ```

## Usage

1. Start the server with Ngrok:
   ```bash
   python run_server.py
   ```

2. The server will output a public Ngrok URL - you need to set up this URL as a webhook in Linear:
   - Go to Linear Settings > API > Webhooks
   - Create a new webhook with the URL from Ngrok + "/webhook" (e.g., `https://internally-wise-spaniel.ngrok.io/webhook`)
   - Select the events you want to trigger the bot (usually "Issues" with "Updated" action)

3. Try making a ticket and adding the `Codegen` label to trigger the agent

## Troubleshooting

- If you encounter issues with the Ngrok tunnel, make sure your Ngrok auth token is correctly set up
- Check the logs for any error messages related to the FastAPI server or webhook processing
- Verify your Linear webhook is correctly pointing to the Ngrok URL + "/webhook" path
- If the agent works with the wrong repository, check that your `TARGET_REPOSITORY` and `REPOSITORY_LANGUAGE` environment variables are set correctly

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.