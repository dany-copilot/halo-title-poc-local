import mcp
from mcp.client.streamable_http import streamablehttp_client
import json
import base64
from bs4 import BeautifulSoup
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# CONFIGURATION (put your real tokens here)
apify_api_token = os.getenv("APIFY_API_TOKEN")  # <-- Get this from https://console.apify.com/account/integrations
smithery_api_key = os.getenv("SMITHERY_API_KEY")  # <-- From https://smithery.ai/dashboard
config = {
  "apifyApiToken": apify_api_token
}
config_b64 = base64.b64encode(json.dumps(config).encode()).decode()

# Create server URL
url = f"https://server.smithery.ai/mcp-server-rag-web-browser/mcp?config={config_b64}&api_key={smithery_api_key}&profile=distinctive-macaw-7uwbc6"

def build_steps(last_name, first_name=None):
    steps = [
        {"goto": {"url": "http://landrecords.co.harrison.ms.us/"}},
        {"wait_for_selector": {"selector": "input[value='Guest Login']", "timeout": 10000}},
        {"click": {"selector": "input[value='Guest Login']"}},
        {"wait_for_selector": {"selector": "a:has-text('Search Records')", "timeout": 10000}},
        {"click": {"selector": "a:has-text('Search Records')"}},
        {"wait_for_selector": {"selector": "#SearchTabs", "timeout": 10000}},
        {"fill": {"selector": "input[name='LastName']", "text": last_name}},
    ]
    if first_name:
        steps.append({"fill": {"selector": "input[name='FirstName']", "text": first_name}})
    steps.extend([
        {"click": {"selector": "input[type='button'][value='Search']"}},
        {"wait_for_selector": {"selector": "#searchResultsTable", "timeout": 10000}},
        {"extract": {"selector": "#searchResultsTable", "attribute": "outer_html"}},
    ])
    return steps

def parse_results_table(table_html):
    soup = BeautifulSoup(table_html, 'html.parser')
    table = soup.find('table')
    results = []
    if table:
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        for row in table.find_all('tr')[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if cells:
                results.append(dict(zip(headers, cells)))
    return results

async def main():
    # --- Setup ---
    last_name = "Smith"
    first_name = None  # or set to a string for full name search

    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        async with mcp.ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            # List available tools
            tools_result = await session.list_tools()
            print(f"Available tools: {', '.join([t.name for t in tools_result.tools])}")

            # Find the browser tool
            browser_tool = None
            for t in tools_result.tools:
                if "browser" in t.name.lower():
                    browser_tool = t.name
                    break
            if not browser_tool:
                print("No browser tool found!")
                return

            # Compose browser steps
            steps = build_steps(last_name, first_name)
            # Send steps to browser tool
            result = await session.invoke_tool(browser_tool, input=json.dumps(steps))

            # Find the extract step output
            outer_html = None
            for step in result.steps:
                if hasattr(step, "output") and step.output:
                    try:
                        out = json.loads(step.output)
                        if isinstance(out, dict) and "outer_html" in out:
                            outer_html = out["outer_html"]
                            break
                    except Exception:
                        continue

            if not outer_html:
                print("No results table found in output.")
                return

            # Parse and print as JSON
            parsed = parse_results_table(outer_html)
            print(json.dumps(parsed, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
