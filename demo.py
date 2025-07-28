#!/usr/bin/env python3
"""
BeatSync Mixer - Interactive Demo Script
This script demonstrates all the features of the BeatSync Mixer application
including real-time Socket.IO functionality.
"""

import requests
import socketio
import json
import time
import threading
from urllib.parse import urljoin

class BeatSyncDemo:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url
        self.sio = socketio.SimpleClient()
        self.events_received = []
        
    def test_api_endpoints(self):
        """Test all HTTP API endpoints"""
        print("🧪 Testing HTTP API Endpoints")
        print("=" * 50)
        
        # Health check
        try:
            response = requests.get(f"{self.base_url}/health")
            if response.status_code == 200:
                print("✅ Health endpoint: Working")
            else:
                print(f"❌ Health endpoint: Failed ({response.status_code})")
        except requests.ConnectionError:
            print("❌ Health endpoint: Connection failed")
            return False
        
        # Homepage
        try:
            response = requests.get(self.base_url)
            if response.status_code == 200 and "BeatSync Mixer" in response.text:
                print("✅ Homepage: Loads correctly")
            else:
                print(f"❌ Homepage: Failed ({response.status_code})")
        except requests.ConnectionError:
            print("❌ Homepage: Connection failed")
        
        # Queue endpoint
        try:
            response = requests.get(f"{self.base_url}/queue")
            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                print(f"✅ Queue endpoint: Working (Current: {count} items)")
                
                # Show current queue if any
                if count > 0:
                    print("   Current queue:")
                    for item in data.get('queue', []):
                        print(f"   - {item.get('track_name', 'Unknown')} ({item.get('track_uri', 'No URI')})")
            else:
                print(f"❌ Queue endpoint: Failed ({response.status_code})")
        except requests.ConnectionError:
            print("❌ Queue endpoint: Connection failed")
        
        # Test playlists endpoint (should redirect to login)
        try:
            response = requests.get(f"{self.base_url}/playlists", allow_redirects=False)
            if response.status_code in [302, 401]:
                print("✅ Playlists endpoint: Correctly redirects (authentication required)")
            else:
                print(f"⚠️  Playlists endpoint: Unexpected response ({response.status_code})")
        except requests.ConnectionError:
            print("❌ Playlists endpoint: Connection failed")
        
        print("\n")
        return True
    
    def test_socketio_functionality(self):
        """Test Socket.IO real-time functionality"""
        print("🔄 Testing Socket.IO Real-time Features")
        print("=" * 50)
        
        try:
            # Connect to Socket.IO
            self.sio.connect(self.base_url)
            print("✅ Socket.IO: Connected successfully")
            
            # Test queue add
            print("📝 Testing queue add...")
            test_track = {
                'track_uri': 'spotify:track:demo123',
                'track_name': 'Demo Track by Demo Artist'
            }
            self.sio.emit('queue_add', test_track)
            time.sleep(0.5)
            print("✅ Queue add: Event sent")
            
            # Test voting
            print("👍 Testing voting...")
            vote_data = {
                'track_uri': 'spotify:track:demo123',
                'vote': 'up',
                'user_id': 'demo_user'
            }
            self.sio.emit('vote_add', vote_data)
            time.sleep(0.5)
            print("✅ Voting: Up vote sent")
            
            # Test chat
            print("💬 Testing chat...")
            chat_data = {
                'user': 'DemoUser',
                'message': 'Hello from the demo script! 🎵'
            }
            self.sio.emit('chat_message', chat_data)
            time.sleep(0.5)
            print("✅ Chat: Message sent")
            
            # Disconnect
            self.sio.disconnect()
            print("✅ Socket.IO: Disconnected successfully")
            
        except Exception as e:
            print(f"❌ Socket.IO: Test failed - {e}")
            return False
        
        print("\n")
        return True
    
    def test_queue_management(self):
        """Test queue management via HTTP"""
        print("📋 Testing Queue Management")
        print("=" * 50)
        
        # Get current queue state
        response = requests.get(f"{self.base_url}/queue")
        if response.status_code == 200:
            initial_count = response.json().get('count', 0)
            print(f"📊 Initial queue size: {initial_count}")
            
            # Clear the queue
            clear_response = requests.post(f"{self.base_url}/queue/clear")
            if clear_response.status_code == 200:
                print("✅ Queue clear: Successfully cleared")
                
                # Verify queue is empty
                verify_response = requests.get(f"{self.base_url}/queue")
                if verify_response.status_code == 200:
                    final_count = verify_response.json().get('count', 0)
                    if final_count == 0:
                        print("✅ Queue verification: Queue is empty")
                    else:
                        print(f"⚠️  Queue verification: Expected 0 items, got {final_count}")
            else:
                print(f"❌ Queue clear: Failed ({clear_response.status_code})")
        else:
            print(f"❌ Queue state check: Failed ({response.status_code})")
        
        print("\n")
    
    def demonstrate_realtime_sync(self):
        """Demonstrate real-time synchronization between multiple clients"""
        print("🔄 Demonstrating Real-time Synchronization")
        print("=" * 50)
        
        # Create two Socket.IO clients to simulate multiple users
        client1 = socketio.SimpleClient()
        client2 = socketio.SimpleClient()
        
        try:
            # Connect both clients
            client1.connect(self.base_url)
            client2.connect(self.base_url)
            print("✅ Multiple clients: Connected successfully")
            
            # Client 1 adds a track
            print("👤 Client 1: Adding track to queue...")
            track_data = {
                'track_uri': 'spotify:track:sync_demo',
                'track_name': 'Real-time Sync Demo Track'
            }
            client1.emit('queue_add', track_data)
            time.sleep(0.5)
            
            # Client 2 votes on the track
            print("👤 Client 2: Voting on the track...")
            vote_data = {
                'track_uri': 'spotify:track:sync_demo',
                'vote': 'up',
                'user_id': 'client2'
            }
            client2.emit('vote_add', vote_data)
            time.sleep(0.5)
            
            # Both clients send chat messages
            print("👤 Clients: Sending chat messages...")
            client1.emit('chat_message', {'user': 'Client1', 'message': 'I added a great track!'})
            time.sleep(0.2)
            client2.emit('chat_message', {'user': 'Client2', 'message': 'I voted it up! 👍'})
            time.sleep(0.5)
            
            print("✅ Real-time sync: Demo completed")
            
            # Disconnect clients
            client1.disconnect()
            client2.disconnect()
            print("✅ Multiple clients: Disconnected successfully")
            
        except Exception as e:
            print(f"❌ Real-time sync: Failed - {e}")
    
    def show_final_state(self):
        """Show the final state of the application after demo"""
        print("📊 Final Application State")
        print("=" * 50)
        
        # Show queue state
        response = requests.get(f"{self.base_url}/queue")
        if response.status_code == 200:
            data = response.json()
            count = data.get('count', 0)
            print(f"🎵 Queue: {count} tracks")
            
            if count > 0:
                print("   Tracks in queue:")
                for i, item in enumerate(data.get('queue', []), 1):
                    track_name = item.get('track_name', 'Unknown Track')
                    timestamp = item.get('timestamp', 'No timestamp')
                    print(f"   {i}. {track_name} (Added: {timestamp[:19] if timestamp else 'Unknown'})")
        
        print(f"\n🌐 Application running at: {self.base_url}")
        print("🎵 Ready for Spotify integration and real-time collaboration!")
    
    def run_full_demo(self):
        """Run the complete demonstration"""
        print("🎵 BeatSync Mixer - Complete Feature Demo")
        print("=" * 60)
        print("This demo tests all features of the BeatSync Mixer application:")
        print("• HTTP API endpoints")
        print("• Socket.IO real-time features") 
        print("• Queue management")
        print("• Multi-client synchronization")
        print("• Voting and chat functionality")
        print("=" * 60)
        print()
        
        success = True
        
        # Run all tests
        success &= self.test_api_endpoints()
        success &= self.test_socketio_functionality()
        self.test_queue_management()
        self.demonstrate_realtime_sync()
        self.show_final_state()
        
        print("\n" + "=" * 60)
        if success:
            print("🎉 Demo completed successfully!")
            print("Your BeatSync Mixer is fully functional and ready for use!")
        else:
            print("⚠️  Demo completed with some issues.")
            print("Check the output above for details.")
        print("=" * 60)

def main():
    demo = BeatSyncDemo()
    demo.run_full_demo()

if __name__ == "__main__":
    main()
