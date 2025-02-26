"""
Custom tools for the CodeAgent to enhance its capabilities.
"""

import logging
import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Type, Annotated
from anthropic import Anthropic
from web_search import brave_search, brave_search_with_content, get_content_for_llm, fetch_documentation_for_llm
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class CustomWebSearchInput(BaseModel):
    """Input schema for the web search tool."""
    query: str = Field(description="The search query")
    fetch_content: bool = Field(default=False, description="Whether to fetch content from search results")

class CustomWebSearchTool(BaseTool):
    """
    A custom web search tool that uses the Brave Search API to perform internet searches.
    This tool can be added to the CodeAgent to give it the ability to search the internet
    for documentation, examples, and best practices.
    """
    name: str = "web_search"
    description: str = "Search the web for information, documentation, or examples."
    args_schema: Type[BaseModel] = CustomWebSearchInput
    
    def __init__(self, api_key: Optional[str] = None, max_results: int = 5):
        """
        Initialize the web search tool.
        
        Args:
            api_key: The Anthropic API key (not used directly, but kept for compatibility)
            max_results: The maximum number of search results to return.
        """
        super().__init__()
        self.max_results = max_results
        self.api_key = api_key
        logger.info("CustomWebSearchTool initialized using web_search module")
    
    def _run(self, query: str, fetch_content: bool = False) -> str:
        """
        The main implementation of the tool.
        
        Args:
            query: The search query.
            fetch_content: Whether to fetch content from search results.
            
        Returns:
            A formatted string with the search results.
        """
        if fetch_content:
            return self.search_with_content(query)
        else:
            return self.search(query)
    
    def search(self, query: str) -> str:
        """
        Search the internet for the given query using the Brave Search API.
        
        Args:
            query: The search query.
            
        Returns:
            A formatted string with the search results.
        """
        logger.info(f"Performing web search for: {query}")
        
        try:
            # Use the brave_search function from web_search.py
            results = asyncio.run(brave_search(query, count=self.max_results))
            return results or "No search results found."
            
        except Exception as e:
            logger.error(f"Error performing web search: {str(e)}")
            return f"Error performing web search: {str(e)}"
    
    def search_with_content(self, query: str) -> str:
        """
        Search the internet and fetch content from the search results.
        
        Args:
            query: The search query.
            
        Returns:
            A formatted string with the search results and content.
        """
        logger.info(f"Performing web search with content for: {query}")
        
        try:
            # Use the get_content_for_llm function from web_search.py
            content = asyncio.run(get_content_for_llm(query, count=self.max_results))
            return content or "No search results or content found."
            
        except Exception as e:
            logger.error(f"Error performing web search with content: {str(e)}")
            return f"Error performing web search with content: {str(e)}"

class CustomDocumentationInput(BaseModel):
    """Input schema for the documentation tool."""
    library: str = Field(description="The name of the library or framework")
    topic: str = Field(description="The specific topic or function to look up")

class CustomDocumentationTool(BaseTool):
    """
    A tool for fetching and parsing documentation from common programming resources.
    This tool can be added to the CodeAgent to give it the ability to fetch documentation
    for specific libraries, frameworks, or APIs.
    """
    name: str = "fetch_documentation"
    description: str = "Fetch documentation for a specific library or framework and topic."
    args_schema: Type[BaseModel] = CustomDocumentationInput
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the documentation tool.
        
        Args:
            api_key: The Anthropic API key to use for parsing documentation.
                     If not provided, it will try to get it from the ANTHROPIC_API_KEY environment variable.
        """
        super().__init__()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required for documentation tool")
        
        self.client = Anthropic(api_key=self.api_key)
        logger.info("CustomDocumentationTool initialized")
    
    def _run(self, library: str, topic: str) -> str:
        """
        The main implementation of the tool.
        
        Args:
            library: The name of the library or framework.
            topic: The specific topic or function to look up.
            
        Returns:
            A string containing the documentation.
        """
        return self.fetch_documentation(library, topic)
    
    def fetch_documentation(self, library: str, topic: str) -> str:
        """
        Fetch documentation for a specific library and topic.
        
        Args:
            library: The name of the library or framework.
            topic: The specific topic or function to look up.
            
        Returns:
            A string containing the documentation.
        """
        logger.info(f"Fetching documentation for {library} - {topic}")
        
        try:
            # First try to use the web_search module to fetch documentation
            query = f"{library} {topic} documentation api reference"
            doc_results = asyncio.run(fetch_documentation_for_llm(query, count=5))
            
            if doc_results and doc_results.get('formatted_content'):
                logger.info(f"Successfully fetched documentation for {library} - {topic} using web_search")
                return doc_results['formatted_content']
            
            # Fallback to using Anthropic's Claude if web search didn't yield good results
            logger.info(f"Falling back to Anthropic API for {library} - {topic} documentation")
            message = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1500,
                system="You are a helpful programming assistant. Your task is to provide accurate documentation for programming libraries and frameworks. Include code examples when relevant.",
                messages=[
                    {"role": "user", "content": f"Provide documentation for the '{topic}' in the '{library}' library or framework. Include code examples and usage patterns."}
                ]
            )
            
            # Extract the documentation from the response
            documentation = message.content[0].text
            
            logger.info(f"Successfully fetched documentation for {library} - {topic}")
            return documentation
            
        except Exception as e:
            logger.error(f"Error fetching documentation: {str(e)}")
            return f"Error fetching documentation for {library} - {topic}: {str(e)}" 