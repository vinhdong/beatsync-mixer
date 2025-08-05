/**
 * Spotify Player Module - Simplified
 */

let player = null;
let deviceId = null;
let accessToken = null;
let currentTrackStartTime = null;

async function initializeSpotifyPlayer() {
  console.log('=== SPOTIFY PLAYER INIT ===');
  console.log('User role:', window.userRole);
  console.log('========================');

  if (window.userRole !== 'host') {
    console.log('Not a host, skipping Spotify player initialization');
    return;
  }
  
  console.log('Initializing Spotify player for host');
  
  try {
    const response = await fetch('/playback/spotify-token');
    const data = await response.json();
    
    if (data.error) {
      console.error('Failed to get access token:', data.error);
      return;
    }
    
    accessToken = data.access_token;
    console.log('Got access token, initializing Web Playback SDK');
    
    await initializeWebPlaybackSDK();
    
  } catch (error) {
    console.error('Error initializing Spotify player:', error);
  }
}

async function initializeWebPlaybackSDK() {
  if (!window.Spotify || !window.Spotify.Player) {
    console.error('Spotify Web Playback SDK not loaded');
    return;
  }
  
  player = new window.Spotify.Player({
    name: 'BeatSync Mixer',
    getOAuthToken: cb => { cb(accessToken); },
    volume: 0.5
  });
  
  player.addListener('ready', ({ device_id }) => {
    console.log('Spotify player ready with Device ID:', device_id);
    deviceId = device_id;
    transferPlaybackToDevice(device_id);
  });
  
  player.addListener('not_ready', ({ device_id }) => {
    console.log('Spotify player not ready with Device ID:', device_id);
  });
  
  player.addListener('player_state_changed', (state) => {
    if (!state) return;
    
    console.log('Player state changed:', state);
    
    // Track end detection removed - no automatic playback
  });
  
  player.connect();
}

async function transferPlaybackToDevice(deviceId) {
  try {
    const response = await fetch('/playback/transfer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        device_id: deviceId
      })
    });
    
    if (response.ok) {
      console.log('Playback transferred to device');
    } else {
      console.error('Failed to transfer playback');
    }
  } catch (error) {
    console.error('Error transferring playback:', error);
  }
}

async function togglePlayback() {
  console.log('Toggle playback called');
}

async function nextTrack() {
  if (window.userRole === 'host') {
    console.log('Manual next track');
    
    // Use the queue-based auto-advance
    if (typeof autoAdvanceToNextSong === 'function') {
      autoAdvanceToNextSong();
    } else {
      console.error('autoAdvanceToNextSong function not found');
    }
  } else {
    showNotification('❌ Only hosts can skip tracks', 'error');
  }
}

async function playTrackFromQueue(trackUri) {
  console.log('=== PLAY TRACK ===');
  console.log('Track URI:', trackUri);
  console.log('==================');

  if (window.userRole !== 'host') {
    alert('Only hosts can control playback');
    return;
  }

  // Extract Spotify track ID from URI
  const uriParts = trackUri.split(':');
  const trackId = uriParts[2];
  
  if (!trackId) {
    console.error('Invalid track ID extracted from URI:', trackUri);
    alert('Invalid track format');
    return;
  }
  
  // Validate that this looks like a Spotify URI
  if (uriParts[0] !== 'spotify' || uriParts[1] !== 'track') {
    console.error('URI does not look like a Spotify track URI:', trackUri);
    alert('Invalid Spotify track URI');
    return;
  }

  try {
    // Simple approach: Just load the Spotify embed
    const spotifyPlayer = document.getElementById('spotify-player');
    const spotifyWrapper = document.getElementById('spotify-embed-wrapper');
    
    if (spotifyPlayer && spotifyWrapper) {
      // Set up UI
      setupPlayerUI();
      
      // Load the track in Spotify embed
      const embedUrl = `https://open.spotify.com/embed/track/${trackId}?utm_source=generator&theme=0&show_cover_art=true`;
      spotifyPlayer.src = embedUrl;
      
      console.log('Loaded track in Spotify embed:', trackUri);
      // Removed notification: showNotification('🎵 Track loaded - click play to start', 'info');
      
      // Record when this track started
      currentTrackStartTime = Date.now();
      
      // Remove track from queue after short delay
      removeTrackFromQueueAfterDelay(trackUri);
    }
    
  } catch (error) {
    console.error('Error in playTrackFromQueue:', error);
    alert('Failed to load track: ' + error.message);
  }
}

function setupPlayerUI() {
  const spotifyWrapper = document.getElementById('spotify-embed-wrapper');
  if (spotifyWrapper) {
    spotifyWrapper.style.display = 'block';
  }
  
  // Show next track button for hosts
  const nextBtn = document.getElementById('next-track-btn');
  if (nextBtn && window.userRole === 'host') {
    nextBtn.style.display = 'inline-block';
  }
  
  // Adjust body padding
  document.body.style.paddingTop = '210px';
}

function removeTrackFromQueueAfterDelay(trackUri) {
  setTimeout(async () => {
    try {
      const response = await fetch(`/queue/remove/${encodeURIComponent(trackUri)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        console.log('Track removed from queue after playback start');
        if (typeof refreshQueueDisplay === 'function') {
          refreshQueueDisplay();
        }
      }
    } catch (error) {
      console.error('Error removing track from queue:', error);
    }
  }, 1000);
}

async function removeTrackFromQueue(trackUri) {
  console.log('Removing track from queue:', trackUri);
  
  if (window.userRole !== 'host') {
    alert('Only hosts can remove tracks');
    return;
  }

  try {
    const response = await fetch(`/queue/remove/${encodeURIComponent(trackUri)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include'
    });

    if (response.ok) {
      console.log('Successfully removed track from queue');
      if (typeof refreshQueueDisplay === 'function') {
        refreshQueueDisplay();
      }
    } else {
      console.log('Failed to remove track from queue:', trackUri);
    }
  } catch (error) {
    console.error('Error removing track from queue:', error);
  }
}

function hideSpotifyPlayer() {
  const spotifyWrapper = document.getElementById('spotify-embed-wrapper');
  if (spotifyWrapper) {
    spotifyWrapper.style.display = 'none';
    document.body.style.paddingTop = '20px';
  }
}

// Export functions
window.initializeSpotifyPlayer = initializeSpotifyPlayer;
window.togglePlayback = togglePlayback;
window.nextTrack = nextTrack;
window.playTrackFromQueue = playTrackFromQueue;
window.removeTrackFromQueue = removeTrackFromQueue;
window.hideSpotifyPlayer = hideSpotifyPlayer;
