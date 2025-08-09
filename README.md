# ActivityWatch MCP Server

This repository provides a [Model Context Protocol](https://platform.openai.com/docs/mcp) server that exposes your local [ActivityWatch](https://activitywatch.net/) data to ChatGPT.

## Tools
- **search** – find window events whose titles match a query
- **fetch** – retrieve the full JSON for a result returned by `search`

These tools follow the ChatGPT connector requirements and can be added as a custom connector in ChatGPT.

## Requirements
- Python 3.11+
- ActivityWatch running on `http://localhost:5600`

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage
Run the MCP server:

```bash
python server.py
```

The server listens on `http://localhost:3000`. Configure ChatGPT to connect to this endpoint as an MCP server and use the `search` and `fetch` tools to query your ActivityWatch data.
