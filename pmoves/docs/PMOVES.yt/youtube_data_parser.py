import json
import re
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

class YouTubeDataParser:
    """
    Parse YouTube video data including transcripts, metadata, and thumbnails
    Compatible with MCP tools and expandable for yt-dlp integration
    """
    
    def __init__(self):
        self.video_data = {}
        self.transcript_segments = []
    
    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return ""
    
    def get_thumbnail_urls(self, video_id: str) -> Dict[str, str]:
        """Generate thumbnail URLs for different qualities"""
        return {
            "default": f"https://img.youtube.com/vi/{video_id}/default.jpg",
            "medium": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            "high": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "standard": f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
            "maxres": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        }
    
    def parse_transcript_text(self, transcript_text: str) -> List[Dict]:
        """
        Parse raw transcript text into timestamped segments
        Handles both single block and pre-segmented transcripts
        """
        segments = []
        
        # Split by sentences or natural breaks
        sentences = re.split(r'(?<=[.!?])\s+', transcript_text)
        
        # Estimate timestamps based on average speaking rate (150 words per minute)
        current_time = 0.0
        words_per_second = 150 / 60  # 2.5 words per second
        
        for i, sentence in enumerate(sentences):
            if sentence.strip():
                word_count = len(sentence.split())
                duration = word_count / words_per_second
                
                segment = {
                    "id": i,
                    "text": sentence.strip(),
                    "start_seconds": round(current_time, 2),
                    "end_seconds": round(current_time + duration, 2),
                    "start": self.seconds_to_timestamp(current_time),
                    "end": self.seconds_to_timestamp(current_time + duration)
                }
                
                segments.append(segment)
                current_time += duration
        
        return segments
    
    def seconds_to_timestamp(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS.mmm format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def parse_youtube_data(self, 
                          url: str,
                          video_info: Dict,
                          transcript_data: Dict,
                          include_embeddings: bool = False) -> Dict:
        """
        Main function to parse all YouTube data into structured format
        
        Args:
            url: YouTube video URL
            video_info: Response from get_video_info MCP tool
            transcript_data: Response from get_transcript MCP tool
            include_embeddings: Whether to include placeholder for embeddings
        
        Returns:
            Dictionary with complete video data structure
        """
        video_id = self.extract_video_id(url)
        thumbnails = self.get_thumbnail_urls(video_id)
        
        # Parse transcript into segments
        transcript_segments = self.parse_transcript_text(transcript_data.get('transcript', ''))
        
        # Create metadata structure
        metadata = {
            "video_id": video_id,
            "watch_url": url,
            "title": video_info.get('title', ''),
            "description": video_info.get('description', ''),
            "uploader": video_info.get('uploader', ''),
            "thumbnails": thumbnails,
            "transcript_full": transcript_data.get('transcript', ''),
            "processed_date": datetime.now().isoformat(),
            "total_segments": len(transcript_segments),
            "estimated_duration_seconds": transcript_segments[-1]['end_seconds'] if transcript_segments else 0
        }
        
        # Add segment data with metadata reference
        for segment in transcript_segments:
            segment['video_id'] = video_id
            segment['watch_url'] = url
            if include_embeddings:
                segment['embedding'] = None  # Placeholder for embeddings
                segment['summary_embedding'] = None  # Placeholder for summary embeddings
        
        return {
            "metadata": metadata,
            "segments": transcript_segments
        }
    
    def export_to_dataframe(self, parsed_data: Dict) -> tuple:
        """
        Export parsed data to pandas DataFrames
        Returns: (metadata_df, segments_df)
        """
        # Metadata DataFrame
        metadata_df = pd.DataFrame([parsed_data['metadata']])
        
        # Segments DataFrame
        segments_df = pd.DataFrame(parsed_data['segments'])
        
        return metadata_df, segments_df
    
    def export_to_csv(self, parsed_data: Dict, base_filename: str):
        """Export to CSV files compatible with your existing structure"""
        metadata_df, segments_df = self.export_to_dataframe(parsed_data)
        
        # Save metadata
        metadata_df.to_csv(f"{base_filename}_metadata.csv", index=False)
        
        # Save segments (matching your existing structure)
        segments_df.to_csv(f"{base_filename}_transcription.csv", index=False)
        
        print(f"Saved metadata to {base_filename}_metadata.csv")
        print(f"Saved transcript segments to {base_filename}_transcription.csv")
    
    def export_to_json(self, parsed_data: Dict, filename: str):
        """Export to JSON for flexible storage"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, indent=2, ensure_ascii=False)
        print(f"Saved complete data to {filename}")


# Example usage with MCP tools data
def process_youtube_video(url: str, video_info: Dict, transcript_data: Dict):
    """
    Process YouTube video using MCP tools data
    
    Example:
        url = "https://www.youtube.com/watch?v=dPL2vRDunMw"
        video_info = {
            "title": "LangExtract: Turn Messy Text into Graph-RAG Insights",
            "description": "...",
            "uploader": "Prompt Engineering"
        }
        transcript_data = {
            "title": "...",
            "transcript": "full transcript text here",
            "next_cursor": None
        }
    """
    parser = YouTubeDataParser()
    
    # Parse all data
    parsed_data = parser.parse_youtube_data(
        url=url,
        video_info=video_info,
        transcript_data=transcript_data,
        include_embeddings=True  # Set to True if you plan to add embeddings
    )
    
    # Export to different formats
    parser.export_to_csv(parsed_data, "LangExtract_video")
    parser.export_to_json(parsed_data, "LangExtract_video_complete.json")
    
    # Get DataFrames for further processing
    metadata_df, segments_df = parser.export_to_dataframe(parsed_data)
    
    # Display sample data
    print("\nMetadata columns:", metadata_df.columns.tolist())
    print("\nSegments columns:", segments_df.columns.tolist())
    print("\nFirst few segments:")
    print(segments_df[['id', 'start', 'end', 'text']].head())
    
    return parsed_data


# Integration with yt-dlp for more comprehensive metadata
def get_enhanced_metadata_ytdlp(url: str) -> Optional[Dict]:
    """
    Get enhanced metadata using yt-dlp (requires: pip install yt-dlp)
    This provides more detailed information than MCP tools
    """
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract relevant fields
            enhanced_metadata = {
                'title': info.get('title'),
                'description': info.get('description'),
                'uploader': info.get('uploader'),
                'uploader_id': info.get('uploader_id'),
                'channel_id': info.get('channel_id'),
                'duration': info.get('duration'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'upload_date': info.get('upload_date'),
                'categories': info.get('categories', []),
                'tags': info.get('tags', []),
                'thumbnail': info.get('thumbnail'),
                'thumbnails': info.get('thumbnails', []),
                'subtitles': list(info.get('subtitles', {}).keys()),
                'automatic_captions': list(info.get('automatic_captions', {}).keys()),
                'chapters': info.get('chapters', []),
                'playlist': info.get('playlist'),
                'playlist_index': info.get('playlist_index'),
            }
            
            return enhanced_metadata
            
    except ImportError:
        print("yt-dlp not installed. Run: pip install yt-dlp")
        return None
    except Exception as e:
        print(f"Error fetching enhanced metadata: {e}")
        return None


# Database insertion helper for Supabase
def prepare_for_supabase(parsed_data: Dict, embedding_dimension: int = 3584):
    """
    Prepare data for Supabase insertion with your vector store setup
    """
    video_record = {
        'video_id': parsed_data['metadata']['video_id'],
        'title': parsed_data['metadata']['title'],
        'description': parsed_data['metadata']['description'],
        'uploader': parsed_data['metadata']['uploader'],
        'thumbnail_url': parsed_data['metadata']['thumbnails']['high'],
        'watch_url': parsed_data['metadata']['watch_url'],
        'metadata': json.dumps(parsed_data['metadata']),
        'created_at': datetime.now().isoformat()
    }
    
    segment_records = []
    for segment in parsed_data['segments']:
        segment_record = {
            'video_id': segment['video_id'],
            'segment_id': segment['id'],
            'text': segment['text'],
            'start_seconds': segment['start_seconds'],
            'end_seconds': segment['end_seconds'],
            'timestamped_url': f"{segment['watch_url']}&t={int(segment['start_seconds'])}s",
            # Embeddings would be added here after generation
            'text_embedding': None,  # Placeholder for 3584-dim vector
            'summary_embedding': None  # Placeholder for summary embedding
        }
        segment_records.append(segment_record)
    
    return video_record, segment_records


if __name__ == "__main__":
    # Example with your data
    example_url = "https://www.youtube.com/watch?v=dPL2vRDunMw"
    
    # These would come from MCP tools
    example_video_info = {
        "title": "LangExtract: Turn Messy Text into Graph-RAG Insights",
        "description": "In this quick tutorial...",
        "uploader": "Prompt Engineering"
    }
    
    example_transcript = {
        "transcript": "Okay, so this is lang extract...",
        "next_cursor": None
    }
    
    # Process the video
    parsed = process_youtube_video(example_url, example_video_info, example_transcript)
    
    # Prepare for database
    video_rec, segment_recs = prepare_for_supabase(parsed)
    print(f"\nPrepared {len(segment_recs)} segments for database insertion")
