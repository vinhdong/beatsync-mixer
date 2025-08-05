/**
 * Main Application Coordinator
 */

// Application initialization
document.addEventListener('DOMContentLoaded', function() {
  console.log('BeatSync Mixer initializing...');
  
  // Set up restart button event listener
  const restartBtn = document.getElementById('host-restart-btn');
  if (restartBtn) {
    restartBtn.addEventListener('click', function(e) {
      e.preventDefault();
      restartSession();
    });
  }
  
  // Initialize UI components
  if (typeof initializeUI === 'function') {
    initializeUI();
  }
  
  // Initialize playlist UI
  if (typeof initializePlaylistUI === 'function') {
    initializePlaylistUI();
  }
  
  // Load custom playlists for hosts
  if (window.userRole === 'host' && typeof loadCustomPlaylists === 'function') {
    loadCustomPlaylists();
  }
  
  // Initialize Spotify player for hosts
  if (window.userRole === 'host' && typeof initializeSpotifyPlayer === 'function') {
    // Wait for Spotify SDK to load
    window.onSpotifyWebPlaybackSDKReady = () => {
      initializeSpotifyPlayer();
    };
    
    // Fallback if SDK is already loaded
    if (window.Spotify) {
      initializeSpotifyPlayer();
    }
  }
  
  // Load initial queue display
  setTimeout(() => {
    if (typeof refreshQueueDisplay === 'function') {
      console.log('Loading initial queue display');
      refreshQueueDisplay();
    }
  }, 1000); // Give time for socket connection and other modules to load
  
  console.log('BeatSync Mixer initialized for role:', window.userRole);
});

// Global utility functions that might be called from HTML onclick handlers
window.currentUser = 'User_' + Math.random().toString(36).substr(2, 9);

// Restart session function (for hosts)
function restartSession() {
  if (!window.socketConnected) {
    alert('Socket not connected! Cannot restart session.');
    return;
  }
  
  const confirmMessage = '⚠️ RESET SESSION\n\nThis will:\n• Clear all sessions for everyone\n• Remove current host\n• Clear the entire queue\n• Reset all votes\n• Clear all chat messages\n• Force all users to reconnect\n\nAre you sure you want to reset the entire session?';
  
  if (confirm(confirmMessage)) {
    try {
      window.socket.emit('restart_session');
    } catch (error) {
      console.error('Error restarting session:', error);
      alert('Failed to restart session: ' + error.message);
    }
  }
}// Legacy support for functions that might be called from the original HTML
function playTrack() {
  // Handled by auto-play system
}

// Export functions
window.playTrack = playTrack;
window.restartSession = restartSession;
