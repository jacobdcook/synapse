import re
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube

log = logging.getLogger(__name__)

class YouTubeHandler:
    @staticmethod
    def extract_video_id(url):
        pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
        match = re.search(pattern, url)
        return match.group(1) if match else None

    @classmethod
    def get_transcript(cls, url):
        video_id = cls.extract_video_id(url)
        if not video_id:
            return None, "Invalid YouTube URL"

        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = " ".join([item['text'] for item in transcript_list])
            
            # Try to get metadata with pytube
            try:
                yt = YouTube(url)
                title = yt.title
                author = yt.author
            except Exception:
                title = f"Video {video_id}"
                author = "Unknown"

            metadata = {
                "id": video_id,
                "title": title,
                "author": author,
                "url": url
            }
            return full_text, metadata
        except Exception as e:
            log.error(f"Failed to fetch YouTube transcript: {e}")
            return None, str(e)

    @classmethod
    def format_as_context(cls, transcript, metadata):
        header = f"--- YOUTUBE CONTEXT: {metadata['title']} by {metadata['author']} ---\n"
        footer = "\n--- END YOUTUBE CONTEXT ---\n"
        return f"{header}{transcript}{footer}"
