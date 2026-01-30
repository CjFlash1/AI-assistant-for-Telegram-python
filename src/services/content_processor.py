import logging
import asyncio
import yt_dlp
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class ContentProcessor:
    @staticmethod
    async def extract_link_metadata(url: str):
        """Extracts metadata using yt-dlp for social media or trafilatura for general web."""
        try:
            # Check if it's a social media link
            social_domains = ['instagram.com', 'tiktok.com', 'youtube.com', 'youtu.be', 'twitter.com', 'x.com', 'facebook.com', 'reddit.com']
            is_social = any(domain in url.lower() for domain in social_domains)

            if is_social:
                logger.info(f"Processing social media link via yt-dlp: {url}")
                return await ContentProcessor._extract_via_ytdlp(url)
            else:
                logger.info(f"Processing general link via trafilatura: {url}")
                return await ContentProcessor._extract_via_trafilatura(url)

        except Exception as e:
            logger.error(f"Error processing link {url}: {e}")
            return None

    @staticmethod
    async def _extract_via_ytdlp(url: str):
        """Extraction for social media/video sites with improved metadata."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            # Don't use extract_flat to get full metadata
            'ignoreerrors': True,
            # Try to get comments/descriptions
            'getcomments': False,  # Can be slow, disabled for now
            'extract_flat': False,  # Get full info
        }
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Run in executor because yt-dlp is synchronous
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

                if not info:
                    logger.warning(f"yt-dlp returned no info for {url}")
                    return await ContentProcessor._extract_via_trafilatura(url)

                # Extract all available fields
                title = info.get('title') or info.get('fulltitle') or 'Social Media Post'
                description = info.get('description') or ''
                uploader = info.get('uploader') or info.get('channel') or info.get('creator') or 'Unknown'
                upload_date = info.get('upload_date', '')
                view_count = info.get('view_count', 0)
                like_count = info.get('like_count', 0)
                comment_count = info.get('comment_count', 0)
                duration = info.get('duration_string') or ''
                platform = info.get('extractor_key') or info.get('extractor') or 'Social'

                # Build rich content summary
                content_parts = [f"Платформа: {platform}"]
                content_parts.append(f"Автор: {uploader}")
                if title and title != 'Social Media Post':
                    content_parts.append(f"Заголовок: {title}")
                if upload_date:
                    # Format: YYYYMMDD -> YYYY-MM-DD
                    formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}" if len(upload_date) == 8 else upload_date
                    content_parts.append(f"Дата: {formatted_date}")
                if duration:
                    content_parts.append(f"Длительность: {duration}")
                if view_count:
                    content_parts.append(f"Просмотры: {view_count:,}")
                if like_count:
                    content_parts.append(f"Лайки: {like_count:,}")
                if description:
                    # Truncate very long descriptions
                    desc_preview = description[:1000] + ('...' if len(description) > 1000 else '')
                    content_parts.append(f"Описание: {desc_preview}")

                content = "\n".join(content_parts)

                # If we got basically nothing useful, try trafilatura
                if not description and title == 'Social Media Post':
                    logger.info(f"yt-dlp got minimal info, trying trafilatura fallback")
                    trafilatura_result = await ContentProcessor._extract_via_trafilatura(url)
                    if trafilatura_result and trafilatura_result.get('content'):
                        return trafilatura_result

                return {
                    "title": title,
                    "description": description,
                    "content": content,
                    "url": url
                }
        except Exception as e:
            logger.warning(f"yt-dlp failed for {url}: {e}")
            return await ContentProcessor._extract_via_trafilatura(url)

    @staticmethod
    async def _extract_via_trafilatura(url: str):
        """Extraction for general web articles/content."""
        try:
            loop = asyncio.get_event_loop()
            downloaded = await loop.run_in_executor(None, lambda: trafilatura.fetch_url(url))
            if downloaded:
                result = await loop.run_in_executor(None, lambda: trafilatura.extract(downloaded, include_comments=False))
                if result:
                    # Get title separately if possible
                    metadata = trafilatura.extract_metadata(downloaded)
                    title = metadata.title if metadata and metadata.title else "Web Article"

                    return {
                        "title": title,
                        "description": "",
                        "content": result,
                        "url": url
                    }
            return None
        except Exception as e:
            logger.error(f"trafilatura failed: {e}")
            return None
