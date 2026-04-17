from typing import Any, Dict
import httpx
from mcp.server.fastmcp import FastMCP
import os
import re
import json

# Initialize FastMCP server
mcp = FastMCP("ip2locationio")

# Constants
IPLIO_API_BASE = "https://api.ip2location.io"
IPLIO_BULK_API_BASE = "https://bulk.ip2location.io"
USER_AGENT = "ip2locationio-app/1.0"

def get_api_key() -> str | None:
    """Retrieve the API key from MCP server config."""
    return os.getenv("IP2LOCATION_API_KEY")

async def make_request(url: str, params: dict[str, str]) -> dict[str, Any] | None:
    """Make a request to the IP2Location.io API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

async def make_bulk_request(url: str, ips: list[str], api_key: str | None) -> dict[str, Any] | None:
    """Make a POST request to the IP2Location.io Bulk API endpoint."""
    params = {"format": "json"}
    if api_key:
        params["key"] = api_key
    
    # Rectified: Dump list to string to match the `data = '["1.1.1.1", ...]'` requirement
    payload_data = json.dumps(ips)
        
    async with httpx.AsyncClient() as client:
        try:
            # We use `content=payload_data` in httpx to send the raw string exactly 
            # like `data=data` does in the requests library.
            response = await client.post(url, params=params, content=payload_data, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

@mcp.tool()
async def get_geolocation(ip: str) -> Dict[str, Any] | str:
    """
    Fetch geolocation for the given IP address(es).
    
    CRITICAL INSTRUCTION FOR AI AGENT: If the user provides multiple IP addresses in their prompt, 
    DO NOT call this tool multiple times sequentially. You MUST batch all IP addresses together 
    into a single comma-separated string and make exactly ONE tool call.

    It helps users to retrieve detailed information such as country, region, city, latitude, longitude, ZIP code, time zone, ASN, and proxy information for any IPv4 or IPv6 address.

    Args:
        ip: The IP address to analyze (IPv4 or IPv6). For multiple IPs, you MUST combine them into a single string separated by commas (e.g., "1.1.1.1, 2.2.2.2").

    Returns:
        A JSON string result includes:
        
        Location & Geography:
        Country, region, district, city, ZIP code, latitude & longitude, time zone.
        
        Network & Connectivity
        ASN (Autonomous System Number), ISP (Internet Service Provider), domain, net speed, IDD code, area code, address type, usage type.
        
        Mobile Information
        MNC (Mobile Network Code), MCC (Mobile Country Code), Mobile Brand.
        
        Currency & Language
        currency code, currency name, currency symbol, language code, language name.
        
        Proxy & Security
        proxy type, last seen, threat level/type, proxy provider, fraud score.
        
        Others
        IAB category, weather, elevation, population and more.
        
        Note that some information may only available in paid plan. Learn more on this in https://www.ip2location.io/pricing.
    """
    # Extract IPs from input (supports comma, space, or newline separation)
    ip_list = [i.strip() for i in re.split(r'[,\s]+', ip) if i.strip()]
    
    if not ip_list:
        return "No valid IP addresses provided."
    
    api_key = get_api_key()
    
    # Standard Flow for a Single IP Request
    if len(ip_list) == 1:
        single_ip = ip_list[0]
        params = {"ip": single_ip}
        if api_key:
            params["key"] = api_key
        else:
            return(f"An API key is needed to use the bulk API.")

        geolocation_result = await make_request(IPLIO_API_BASE, params)

        if not geolocation_result:
            return f"Unable to fetch geolocation for IP {single_ip}."

        return geolocation_result

    # Enhanced Flow for Multiple IP Addresses
    # 1. Try the bulk endpoint first
    bulk_result = await make_bulk_request(IPLIO_BULK_API_BASE, ip_list, api_key)
    
    if bulk_result:
        return bulk_result
    
    # 2. Fallback: If bulk fails, query one by one
    fallback_results = {}
    for single_ip in ip_list:
        params = {"ip": single_ip}
        if api_key:
            params["key"] = api_key
            
        res = await make_request(IPLIO_API_BASE, params)
        if res:
            fallback_results[single_ip] = res
        else:
            fallback_results[single_ip] = {"error": f"Unable to fetch geolocation for IP {single_ip}."}
            
    return fallback_results

    geolocation_result = await make_request(IPLIO_API_BASE, params)

    if not geolocation_result:
        return f"Unable to fetch geolocation for IP {ip}."

    return geolocation_result

if __name__ == "__main__":
    mcp.run(transport='stdio')
