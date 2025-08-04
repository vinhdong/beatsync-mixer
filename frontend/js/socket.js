/**
 * Socket.IO Connection and Events Module
 */

// Socket initialization
const socket = io();
let socketConnected = false;
const socketId = Math.random().toString(36).substr(2, 8);

console.log(`[SOCKET ${socketId}] Socket created for role:`, window.userRole);

// Connection events
socket.on('connect', function() {
  console.log(`[SOCKET ${socketId}] Connected`);
  socketConnected = true;
});

socket.on('disconnect', function() {
  console.log(`[SOCKET ${socketId}] Disconnected`);
  socketConnected = false;
});

socket.on('error', function(error) {
  console.error('Socket error:', error);
  
  if (error.message) {
    alert('Error: ' + error.message);
  }
  
  if (error.message && error.message.includes('Authentication')) {
    fetch('/session-info')
      .then(response => response.json())
      .then(sessionData => {
        console.log('Session data after auth error:', sessionData);
      })
      .catch(err => console.error('Failed to fetch session info:', err));
  }
});

// Playback events
socket.on("playback_started", data => {
  console.log('Playback started:', data);
  
  if (data.track_uri && typeof updateNowPlaying === 'function') {
    updateNowPlaying(data);
  }
});

socket.on("playback_paused", data => {
  console.log('Playback paused:', data);
  if (typeof updatePlayPauseButton === 'function') {
    updatePlayPauseButton(false);
  }
});

socket.on("playback_resumed", data => {
  console.log('Playback resumed:', data);
  if (typeof updatePlayPauseButton === 'function') {
    updatePlayPauseButton(true);
  }
});

// Queue events
socket.on("queue_updated", data => {
  console.log('Queue updated:', data);
  if (typeof refreshQueueDisplay === 'function') {
    refreshQueueDisplay();
  }
});

socket.on("track_added", data => {
  console.log('Track added:', data);
  if (typeof loadQueue === 'function') {
    loadQueue();
  }
});

socket.on("track_removed", data => {
  console.log('Track removed:', data);
  if (typeof loadQueue === 'function') {
    loadQueue();
  }
});

socket.on("votes_updated", data => {
  console.log('Votes updated:', data);
  if (typeof updateVoteDisplay === 'function') {
    updateVoteDisplay(data);
  }
});

socket.on("queue_cleared", () => {
  console.log('Queue cleared');
  if (typeof loadQueue === 'function') {
    loadQueue();
  }
});

// Chat events
socket.on("chat_message", data => {
  console.log('Chat message received:', data);
  if (typeof displayChatMessage === 'function') {
    displayChatMessage(data);
  }
});

// Export socket for global access
window.socket = socket;
window.socketConnected = socketConnected;
