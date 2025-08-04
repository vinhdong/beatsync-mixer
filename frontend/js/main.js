/**
 * Main Application Coordinator
 */

// Application initialization
document.addEventListener('DOMContentLoaded', function() {
  console.log('BeatSync Mixer initializing...');
  
  // Initialize UI components
  if (typeof initializeUI === 'function') {
    initializeUI();
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
  
  console.log('BeatSync Mixer initialized for role:', window.userRole);
});

// Global utility functions that might be called from HTML onclick handlers
window.currentUser = 'User_' + Math.random().toString(36).substr(2, 9);

// Legacy support for functions that might be called from the original HTML
function playTrack() {
  console.log('playTrack() called - handled by auto-play system');
}

function debugPlayerState() {
  console.log('=== PLAYER DEBUG ===');
  console.log('Access Token:', window.accessToken ? 'Present' : 'Missing');
  console.log('Device ID:', window.deviceId || 'Missing');
  console.log('Player Object:', window.player ? 'Present' : 'Missing');
  console.log('Role:', window.userRole);
  console.log('Socket Connected:', window.socketConnected);
  console.log('=== END DEBUG ===');
}

// Export for debugging
window.debugPlayer = debugPlayerState;
window.playTrack = playTrack;
