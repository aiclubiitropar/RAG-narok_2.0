import requests
import os
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def google_search2(query: str) -> str:
    """
    Uses Zenserp API to perform a Google Search. Fallback if SerpAPI fails.
    """
    api_key = os.getenv('ZEN_API_KEY')
    if not api_key:
        return '[Zenserp Search: Missing API key]'
        
    headers = {"apikey": api_key}
    params = {"q": query, "num": 3}
    try:
        response = requests.get('https://app.zenserp.com/api/v2/search', headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get('organic', [])
        if not results:
            return '[Zenserp Search: No results found]'
        out = []
        for r in results[:3]:
            title = r.get('title', '')
            link = r.get('url', '')
            snippet = r.get('description', '')
            out.append(f"- {title}\n{snippet}\n{link}")
        return '\n\n'.join(out)
    except Exception as e:
        logger.error(f"Zenserp Error: {e}")
        return f'[Zenserp Search Error: {str(e)}]'

def google_search3(query: str) -> str:
    """
    Uses Google Custom Search API. Final fallback.
    """
    api_key = os.getenv('GOOGLE_SEARCH_ENGINE_API_KEY')
    search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
    if not api_key or not search_engine_id:
        return '[Google Custom Search API: Missing API key or Search Engine ID]'

    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={search_engine_id}&q={query}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get('items', [])
        if not results:
            return '[Google Custom Search API: No results found]'
        out = []
        for item in results[:3]:
            title = item.get('title', '')
            link = item.get('link', '')
            snippet = item.get('snippet', '')
            out.append(f"- {title}\n{snippet}\n{link}")
        return '\n\n'.join(out)
    except Exception as e:
        logger.error(f"Google Custom Search API Error: {e}")
        return f'[Google Custom Search API Error: {str(e)}]'

@tool
def google_search_tool(query: str) -> str:
    """
    Use this tool to perform a Google web search if the local campus/academic databases 
    have no relevant information, or if you need real-time/global internet information.
    """
    logger.info(f"Querying Google Search for: {query}")
    
    # 1. Try Google Custom Search (Primary)
    google_custom_result = google_search3(query)
    if not ("Error" in google_custom_result or "Missing API key" in google_custom_result or "No results found" in google_custom_result):
        return google_custom_result
        
    logger.info("Google Custom Search failed or missing keys. Falling back to SerpAPI.")
    
    # 2. Try SerpAPI (Fallback 1)
    api_key = os.getenv('SERPAPI_API_KEY')
    if api_key:
        url = "https://serpapi.com/search"
        params = {
            'q': query,
            'api_key': api_key,
            'engine': 'google',
            'num': 3
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('organic_results', [])
            if results:
                out = []
                for r in results[:3]:
                    title = r.get('title', '')
                    link = r.get('link', '')
                    snippet = r.get('snippet', '')
                    out.append(f"- {title}\n{snippet}\n{link}")
                return '\n\n'.join(out)
        except Exception as e:
            logger.error(f"SerpAPI Error: {e}")
            
    logger.info("SerpAPI failed or missing keys. Falling back to Zenserp.")
            
    # 3. Try Zenserp (Fallback 2)
    zenserp_result = google_search2(query)
    if not ("Error" in zenserp_result or "Missing API key" in zenserp_result or "No results found" in zenserp_result):
        return zenserp_result
        
    return "[Google Search: All engines failed or returned no results]"
