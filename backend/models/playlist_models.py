"""
Playlist models for BeatSync Mixer.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database_config import Base


class CustomPlaylist(Base):
    __tablename__ = "custom_playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship to user
    user = relationship("User", backref="custom_playlists")
    
    def __repr__(self):
        return f"<CustomPlaylist {self.name}>"


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"
    
    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("custom_playlists.id"), nullable=False)
    track_uri = Column(String(255), nullable=False)  # Spotify URI
    track_name = Column(String(255), nullable=False)
    track_artist = Column(String(255), nullable=False)
    track_album = Column(String(255))
    track_duration = Column(Integer)  # Duration in milliseconds
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    position = Column(Integer, default=0)  # Track order in playlist
    
    # Relationship to playlist
    playlist = relationship("CustomPlaylist", backref="tracks")
    
    def __repr__(self):
        return f"<PlaylistTrack {self.track_name}>"
