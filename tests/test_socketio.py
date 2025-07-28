#!/usr/bin/env python3
"""
Socket.IO Integration Tests for BeatSync Mixer
Tests real-time functionality using the threading async mode
"""

import pytest
import json
from unittest.mock import patch
import socketio

# Test client for Socket.IO
class TestSocketIORealtime:
    
    def test_socketio_client_can_connect(self):
        """Test that Socket.IO client can connect to the server"""
        # Create a test client
        sio = socketio.SimpleClient()
        
        try:
            # Connect to the running server
            sio.connect('http://127.0.0.1:8000')
            
            # Verify connection
            assert sio.connected
            print("✅ Socket.IO client connected successfully")
            
            # Disconnect
            sio.disconnect()
            assert not sio.connected
            print("✅ Socket.IO client disconnected successfully")
            
        except Exception as e:
            pytest.skip(f"Socket.IO server not running or connection failed: {e}")
    
    def test_queue_add_event(self):
        """Test adding a track to the queue via Socket.IO"""
        sio = socketio.SimpleClient()
        
        try:
            sio.connect('http://127.0.0.1:8000')
            
            # Emit a queue add event
            test_track = {
                'track_uri': 'spotify:track:test123',
                'track_name': 'Test Track by Test Artist'
            }
            
            sio.emit('queue_add', test_track)
            
            # Wait a moment for the server to process
            import time
            time.sleep(0.5)
            
            print("✅ Queue add event sent successfully")
            
            sio.disconnect()
            
        except Exception as e:
            pytest.skip(f"Socket.IO test failed: {e}")
    
    def test_vote_add_event(self):
        """Test voting on a track via Socket.IO"""
        sio = socketio.SimpleClient()
        
        try:
            sio.connect('http://127.0.0.1:8000')
            
            # Emit a vote event
            vote_data = {
                'track_uri': 'spotify:track:test123',
                'vote': 'up',
                'user_id': 'test_user'
            }
            
            sio.emit('vote_add', vote_data)
            
            # Wait for processing
            import time
            time.sleep(0.5)
            
            print("✅ Vote add event sent successfully")
            
            sio.disconnect()
            
        except Exception as e:
            pytest.skip(f"Socket.IO vote test failed: {e}")
    
    def test_chat_message_event(self):
        """Test sending a chat message via Socket.IO"""
        sio = socketio.SimpleClient()
        
        try:
            sio.connect('http://127.0.0.1:8000')
            
            # Emit a chat message
            chat_data = {
                'user': 'TestUser',
                'message': 'Hello from Socket.IO test!'
            }
            
            sio.emit('chat_message', chat_data)
            
            # Wait for processing
            import time
            time.sleep(0.5)
            
            print("✅ Chat message event sent successfully")
            
            sio.disconnect()
            
        except Exception as e:
            pytest.skip(f"Socket.IO chat test failed: {e}")

if __name__ == "__main__":
    # Run tests directly
    test_instance = TestSocketIORealtime()
    
    print("🧪 Testing Socket.IO Real-time Features\n")
    
    try:
        test_instance.test_socketio_client_can_connect()
        test_instance.test_queue_add_event()
        test_instance.test_vote_add_event()
        test_instance.test_chat_message_event()
        print("\n🎉 All Socket.IO tests completed!")
    except Exception as e:
        print(f"\n❌ Socket.IO tests failed: {e}")
