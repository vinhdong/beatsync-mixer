/**
 * Socket.IO Connection and Events Module
 */

// Socket initialization
const socket = io();
let socketConnected = false;
const socketId = Math.random().toString(36).substr(2, 8);

// Make socket globally accessible
window.socket = socket;
window.socketConnected = socketConnected;

console.log(`[SOCKET ${socketId}] Socket created for role:`, window.userRole);

// Connection events
socket.on('connect', function() {
  console.log(`[SOCKET ${socketId}] Connected`);
  socketConnected = true;
  window.socketConnected = true;
  
  // Update connection status
  const statusElement = document.querySelector('.connection-status');
  if (statusElement) {
    statusElement.textContent = 'Connected';
  }
  
  // Load chat history after connection
  socket.emit("load_chat_history");
  
  // Load queue display on initial connection
  if (typeof refreshQueueDisplay === 'function') {
    console.log('Loading initial queue on socket connection');
    setTimeout(() => refreshQueueDisplay(), 500); // Small delay to ensure DOM is ready
  }
});

socket.on('disconnect', function() {
  console.log(`[SOCKET ${socketId}] Disconnected`);
  socketConnected = false;
  window.socketConnected = false;
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

// Handle display name updates for listeners
socket.on("display_name_updated", data => {
  console.log('Display name updated:', data.display_name);
  window.displayName = data.display_name;
  
  // Update the UI to show the new name
  if (typeof updateUserDisplayName === 'function') {
    updateUserDisplayName(data.display_name);
  }
  
  // Update welcome message if it exists
  const nameSpan = document.querySelector('.user-name');
  if (nameSpan) {
    nameSpan.innerHTML = `👋 Welcome, <strong>${data.display_name}</strong>!`;
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
  if (typeof refreshQueueDisplay === 'function') {
    refreshQueueDisplay();
  }
});

socket.on("track_removed", data => {
  console.log('Track removed:', data);
  if (typeof refreshQueueDisplay === 'function') {
    refreshQueueDisplay();
  }
});

socket.on("vote_updated", data => {
  console.log('Vote updated:', data);
  if (typeof updateVoteDisplay === 'function') {
    updateVoteDisplay(data);
  }
  
  // Trigger queue reordering with animations after a brief delay
  setTimeout(() => {
    if (typeof reorderQueueByVotes === 'function') {
      reorderQueueByVotes();
    }
  }, 100);
});

socket.on("vote_success", data => {
  console.log('Vote successful:', data);
});

socket.on("queue_cleared", () => {
  console.log('Queue cleared');
  if (typeof refreshQueueDisplay === 'function') {
    refreshQueueDisplay();
  }
});

socket.on("queue_reordered", () => {
  console.log('Queue reordered due to voting');
  if (typeof reorderQueueByVotes === 'function') {
    reorderQueueByVotes();
  } else if (typeof refreshQueueDisplay === 'function') {
    refreshQueueDisplay();
  }
});

// Chat events
socket.on("chat_message", data => {
  console.log('Chat message received:', data);
  if (typeof displayChatMessage === 'function') {
    displayChatMessage(data);
  }
});

socket.on("chat_history", data => {
  console.log('Chat history received:', data);
  if (typeof loadChatHistory === 'function') {
    loadChatHistory(data.messages);
  }
});

// Session restart handling
socket.on("session_restarted", data => {
  console.log('Session restarted:', data);
  
  // Show notification
  if (typeof showNotification === 'function') {
    showNotification(`🔄 ${data.message}`, 'info');
  }
  
  // Redirect to home page after a short delay
  setTimeout(() => {
    window.location.href = '/';
  }, 3000);
});

// Error handling
socket.on("error", data => {
  console.log('Socket error:', data);
  
  if (data.message) {
    // Show error notification if showNotification function exists
    if (typeof showNotification === 'function') {
      showNotification(`❌ ${data.message}`, 'error');
    } else {
      alert(`Error: ${data.message}`);
    }
  }
});

// Session restart event listener
socket.on('session_restarted', function(data) {
  console.log('Session restarted:', data);
  alert('Session has been restarted! The page will redirect you to role selection.');
  window.location.href = '/select-role';
});

// Export socket for global access
window.socket = socket;
window.socketConnected = socketConnected;
