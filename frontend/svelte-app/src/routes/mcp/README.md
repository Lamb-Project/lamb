# MCP Testing Interface

This directory contains the MCP (Model Context Protocol) testing interface for the LAMB system.

## Overview

The MCP testing interface allows you to:

1. **Check MCP Server Status** - View the current status and capabilities of the LAMB MCP server
2. **Test MCP Prompts** - Browse available LAMB assistants exposed as MCP prompts and test them with custom inputs
3. **Test MCP Tools** - Interact with available MCP tools (when implemented)
4. **Browse MCP Resources** - View available MCP resources (when implemented)

## Key Features

### Prompt Testing

- Lists all LAMB assistants as MCP prompts
- Allows testing prompts with custom user input
- Shows the fully crafted prompt with RAG context (instead of LLM response)
- Displays the result in a formatted JSON view

### Authentication

- Uses the same authentication system as the rest of the LAMB frontend
- Automatically includes the API key from the configuration

### Error Handling

- Displays clear error messages for failed requests
- Shows loading states during API calls

## Usage

1. Navigate to `/mcp` in the LAMB frontend
2. The page will automatically load the MCP server status
3. Click on the "Prompts" tab to see available assistants
4. Select a prompt to test it with custom input
5. View the fully crafted prompt result

## Technical Details

- **API Base URL**: Uses `lambServer` from the configuration (typically `http://localhost:9099`)
- **Endpoints**: Calls `/lamb/v1/mcp/*` endpoints
- **Authentication**: Bearer token authentication using user authentication tokens (lambApiKey removed for security)
- **Framework**: Built with Svelte 5 and Tailwind CSS

## Files

- `+page.svelte` - Main MCP testing interface component
- `README.md` - This documentation file
