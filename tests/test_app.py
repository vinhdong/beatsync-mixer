import pytest
import json
import os

# Set test environment before importing app
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['FLASK_SECRET'] = 'test-secret'
os.environ['SPOTIFY_CLIENT_ID'] = 'test-client-id'
os.environ['SPOTIFY_CLIENT_SECRET'] = 'test-client-secret'
os.environ['SPOTIFY_REDIRECT_URI'] = 'http://localhost:8000/callback'
os.environ['LASTFM_API_KEY'] = 'test-lastfm-key'
os.environ['LASTFM_SHARED_SECRET'] = 'test-lastfm-secret'

# Force threading mode for tests to avoid eventlet issues
os.environ['FLASK_SOCKETIO_ASYNC_MODE'] = 'threading'

from app import app, SessionLocal, QueueItem, Vote, ChatMessage, Base, engine


@pytest.fixture
def client():
    """Create a test client"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            # Create all tables for testing
            Base.metadata.create_all(engine)
            yield client
            # Clean up after test
            Base.metadata.drop_all(engine)


@pytest.fixture  
def socketio_client():
    """Create a Socket.IO test client - placeholder for future implementation"""
    # TODO: Implement Socket.IO testing when eventlet compatibility is resolved
    pass


class TestHealthEndpoint:
    """Test the health check endpoint"""
    
    def test_health_returns_200(self, client):
        """Health endpoint should return 200 OK"""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestPlaylistsEndpoint:
    """Test playlist-related endpoints"""
    
    def test_playlists_redirects_when_not_logged_in(self, client):
        """Playlists endpoint should redirect when user is not logged in"""
        response = client.get('/playlists')
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_playlist_tracks_redirects_when_not_logged_in(self, client):
        """Playlist tracks endpoint should redirect when user is not logged in"""
        response = client.get('/playlists/test-playlist-id/tracks')
        assert response.status_code == 302
        assert '/login' in response.location


class TestQueueEndpoints:
    """Test queue management endpoints"""
    
    def test_queue_endpoint_returns_empty_queue(self, client):
        """Queue endpoint should return empty queue initially"""
        response = client.get('/queue')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] == 0
        assert data['queue'] == []
    
    def test_clear_queue_endpoint(self, client):
        """Clear queue endpoint should require host authentication"""
        # Add some test data first
        db = SessionLocal()
        test_item = QueueItem(
            track_uri='spotify:track:test123',
            track_name='Test Song'
        )
        db.add(test_item)
        db.commit()
        db.close()
        
        # Clear the queue without authentication should fail
        response = client.post('/queue/clear')
        assert response.status_code == 403
        # abort(403) returns HTML, not JSON
        assert 'Forbidden' in response.data.decode('utf-8')
        
        # Verify queue still has items (wasn't cleared)
        response = client.get('/queue')
        data = json.loads(response.data)
        assert data['count'] == 1  # Item should still be there since clear was blocked


class TestSocketIOEvents:
    """Test Socket.IO functionality"""
    
    def test_socketio_import_works(self):
        """Test that Socket.IO can be imported without errors"""
        try:
            from app import socketio
            assert socketio is not None
        except Exception as e:
            pytest.skip(f"Socket.IO not available in test environment: {e}")
    
    # TODO: Add more comprehensive Socket.IO tests when eventlet compatibility is resolved
    # For now, the Socket.IO functionality can be tested manually or in integration tests


class TestDatabaseModels:
    """Test database models and persistence"""
    
    def test_queue_item_creation(self, client):
        """Test QueueItem model creation and persistence"""
        db = SessionLocal()
        
        item = QueueItem(
            track_uri='spotify:track:test123',
            track_name='Test Song - Test Artist'
        )
        db.add(item)
        db.commit()
        
        # Retrieve and verify
        retrieved = db.query(QueueItem).filter_by(track_uri='spotify:track:test123').first()
        assert retrieved is not None
        assert retrieved.track_name == 'Test Song - Test Artist'
        assert retrieved.timestamp is not None
        
        db.close()
    
    def test_vote_creation(self, client):
        """Test Vote model creation and persistence"""
        db = SessionLocal()
        
        vote = Vote(
            track_uri='spotify:track:test123',
            vote_type='up',
            user_id='test_user'
        )
        db.add(vote)
        db.commit()
        
        # Retrieve and verify
        retrieved = db.query(Vote).filter_by(track_uri='spotify:track:test123').first()
        assert retrieved is not None
        assert retrieved.vote_type == 'up'
        assert retrieved.user_id == 'test_user'
        
        db.close()
    
    def test_chat_message_creation(self, client):
        """Test ChatMessage model creation and persistence"""
        db = SessionLocal()
        
        message = ChatMessage(
            user='TestUser',
            message='Hello, world!'
        )
        db.add(message)
        db.commit()
        
        # Retrieve and verify
        retrieved = db.query(ChatMessage).filter_by(user='TestUser').first()
        assert retrieved is not None
        assert retrieved.message == 'Hello, world!'
        assert retrieved.timestamp is not None
        
        db.close()


class TestFrontendServing:
    """Test frontend file serving"""
    
    def test_index_page_loads(self, client):
        """Index page should load and contain expected content"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'BeatSync Mixer' in response.data
        assert b'Connect with Spotify' in response.data


class TestLastFMRecommendations:
    """Test Last.fm recommendations functionality"""
    
    def test_recommend_endpoint_with_valid_track(self, client):
        """Test recommendations endpoint with a valid track in queue"""
        # First, add a track to the queue with proper format
        db = SessionLocal()
        test_track = QueueItem(
            track_uri='spotify:track:test123',
            track_name='Radiohead — Creep'  # Artist — Title format
        )
        db.add(test_track)
        db.commit()
        db.close()
        
        # Mock the entire Last.fm network and track objects
        import unittest.mock
        
        # Create mock objects that match the expected interface
        mock_similar_track = unittest.mock.Mock()
        mock_similar_track.item.artist.name = 'Test Artist'
        mock_similar_track.item.title = 'Test Song'
        mock_similar_track.item.get_url.return_value = 'https://last.fm/test'
        
        mock_track = unittest.mock.Mock()
        mock_track.get_similar.return_value = [mock_similar_track]
        
        with unittest.mock.patch('app.lastfm') as mock_lastfm:
            mock_lastfm.get_track.return_value = mock_track
            
            # Test the recommendations endpoint
            response = client.get('/recommend/spotify:track:test123')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert 'recommendations' in data
            assert len(data['recommendations']) == 1
            assert data['recommendations'][0]['artist'] == 'Test Artist'
            assert data['recommendations'][0]['title'] == 'Test Song'
            assert data['recommendations'][0]['url'] == 'https://last.fm/test'
            
            # Verify the mock was called correctly
            mock_lastfm.get_track.assert_called_once_with('Radiohead', 'Creep')
    
    def test_recommend_endpoint_track_not_found(self, client):
        """Test recommendations endpoint with non-existent track"""
        response = client.get('/recommend/spotify:track:nonexistent')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['error'] == 'Track not found'
    
    def test_recommend_endpoint_invalid_track_format(self, client):
        """Test recommendations endpoint with invalid track name format"""
        # Add a track with invalid format (no " — " separator)
        db = SessionLocal()
        test_track = QueueItem(
            track_uri='spotify:track:invalid',
            track_name='Invalid Track Name'  # Missing " — " separator
        )
        db.add(test_track)
        db.commit()
        db.close()
        
        response = client.get('/recommend/spotify:track:invalid')
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['error'] == 'Invalid track name format'


if __name__ == '__main__':
    pytest.main([__file__])
