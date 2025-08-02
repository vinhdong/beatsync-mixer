#!/usr/bin/env python3
"""
Simple test of Last.fm API functionality
"""

import os
import pylast

# Load environment variables from local .env
from dotenv import load_dotenv
load_dotenv()

def test_lastfm_basic():
    """Test basic Last.fm functionality"""
    print("🎵 Testing Last.fm API connectivity...")
    
    # Initialize Last.fm client
    try:
        lastfm = pylast.LastFMNetwork(
            api_key=os.getenv("LASTFM_API_KEY"),
            api_secret=os.getenv("LASTFM_SHARED_SECRET")
        )
        
        print(f"API Key: {os.getenv('LASTFM_API_KEY')[:10]}...")
        print(f"Secret: {os.getenv('LASTFM_SHARED_SECRET')[:10]}...")
        
        # Test with a well-known track
        artist = "Radiohead"
        title = "Creep"
        
        print(f"Getting track: {artist} - {title}")
        track = lastfm.get_track(artist, title)
        
        print(f"Track found: {track.title} by {track.artist}")
        
        # Get similar tracks
        print("Getting similar tracks...")
        similar_tracks = track.get_similar(limit=5)
        
        print(f"Found {len(similar_tracks)} similar tracks:")
        for i, similar in enumerate(similar_tracks, 1):
            print(f"   {i}. {similar.item.artist.name} - {similar.item.title}")
            print(f"      URL: {similar.item.get_url()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_lastfm_basic()
    if success:
        print("\n✅ Last.fm API is working!")
    else:
        print("\n❌ Last.fm API test failed!")
