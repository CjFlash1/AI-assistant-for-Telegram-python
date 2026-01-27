import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class ContentProcessor:
    @staticmethod
    def extract_link_metadata(url: str):
        """Extracts title, description, and OG tags from a URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            title = soup.title.string if soup.title else ""

            # Try OG tags first
            og_title = soup.find("meta", property="og:title")
            og_desc = soup.find("meta", property="og:description")

            if og_title:
                title = og_title["content"]

            description = ""
            if og_desc:
                description = og_desc["content"]
            else:
                meta_desc = soup.find("meta", name="description")
                if meta_desc:
                    description = meta_desc["content"]

            # Simple text extraction
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()

            text_content = soup.get_text(separator=' ', strip=True)[:5000] # Limit content length

            return {
                "title": title,
                "description": description,
                "content": text_content,
                "url": url
            }

        except Exception as e:
            logger.error(f"Error processing link {url}: {e}")
            return None
