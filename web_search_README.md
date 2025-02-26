# Web Search Module for LLM Agent

This module provides web search capabilities for the LLM agent, allowing it to search the internet for documentation, examples, and best practices.

## Overview

The web search functionality is implemented in two main components:

1. **web_search.py**: Core implementation of web search using the Brave Search API
2. **custom_tools.py**: Integration with the CodeAgent through tool classes

## Features

- Search the web using the Brave Search API
- Fetch and extract content from search results
- Format content for LLM consumption
- Specialized documentation search for programming libraries and APIs
- Rate limiting and retry mechanisms to handle API limitations
- Content truncation to fit within LLM context windows

## Usage

### Basic Search

```python
from web_search import brave_search
import asyncio

results = asyncio.run(brave_search("Python asyncio tutorial", count=5))
print(results)
```

### Search with Content Retrieval

```python
from web_search import get_content_for_llm
import asyncio

content = asyncio.run(get_content_for_llm("Python asyncio tutorial", count=3))
print(content)
```

### Documentation Search

```python
from web_search import fetch_documentation_for_llm
import asyncio

doc_results = asyncio.run(fetch_documentation_for_llm("Python asyncio tutorial", count=3))
print(doc_results['formatted_content'])
```

## Integration with CodeAgent

The web search functionality is integrated with the CodeAgent through the `CustomWebSearchTool` and `CustomDocumentationTool` classes in `custom_tools.py`.

```python
from custom_tools import CustomWebSearchTool, CustomDocumentationTool
from codegen import CodeAgent, Codebase

# Initialize the tools
web_search_tool = CustomWebSearchTool()
doc_tool = CustomDocumentationTool()

# Add the tools to the agent
agent = CodeAgent(codebase, tools=[web_search_tool, doc_tool])

# Run the agent
agent.run("Implement a feature that...")
```

## Environment Variables

The following environment variables are required:

- `BRAVE_SEARCH_API_KEY`: API key for the Brave Search API
- `ANTHROPIC_API_KEY`: API key for Anthropic's Claude (used as fallback for documentation)

## Implementation Details

### Web Search Flow

1. Query is sent to the Brave Search API
2. Search results are retrieved
3. Content from each search result URL is fetched and extracted
4. Content is formatted for LLM consumption
5. Results are returned to the agent

### Documentation Search Flow

1. Query is constructed with the library and topic
2. Search results are retrieved from Brave Search API
3. Content from documentation URLs is fetched and extracted
4. Content is formatted specifically for documentation consumption
5. If web search doesn't yield good results, fallback to Anthropic's Claude
6. Results are returned to the agent 