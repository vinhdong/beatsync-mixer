"""
Music playback state models for BeatSync Mixer.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from .database_config import Base


class CurrentlyPlaying(Base):
    __tablename__ = "currently_playing"
    
    id = Column(Integer, primary_key=True, index=True)
    track_uri = Column(String, nullable=False)
    track_name = Column(String, nullable=False)
    is_playing = Column(String, nullable=False)  # 'true' or 'false'
    device_id = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<CurrentlyPlaying {self.track_name} ({'playing' if self.is_playing == 'true' else 'paused'})>"
