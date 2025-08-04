/**
 * Spotify Player Module
 */

let player = null;
let deviceId = null;
let accessToken = null;
let progressInterval = null;
let trackEndInterval = null;

async function initializeSpotifyPlayer() {
  if (window.userRole !== 'host') {
    console.log('Not a host, skipping Spotify player initialization');
    return;
  }
  
  console.log('Initializing Spotify player for host');
  
  try {
    const response = await fetch('/playback/token');
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
    updateConnectionStatus('Connected');
    enablePlaybackControls(true);
  });
  
  player.addListener('not_ready', ({ device_id }) => {
    console.log('Spotify player not ready with Device ID:', device_id);
    updateConnectionStatus('Disconnected');
    enablePlaybackControls(false);
  });
  
  player.addListener('player_state_changed', (state) => {
    if (!state) return;
    
    console.log('Player state changed:', state);
    
    updateNowPlaying(state.track_window.current_track);
    updatePlayPauseButton(!state.paused);
    updateProgress(state.position, state.track_window.current_track.duration_ms);
    
    if (!state.paused) {
      startProgressTracking();
      startTrackEndDetection();
    } else {
      stopProgressTracking();
      stopTrackEndDetection();
    }
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
  if (!player) return;
  
  try {
    await player.togglePlay();
  } catch (error) {
    console.error('Error toggling playback:', error);
  }
}

async function nextTrack() {
  if (window.userRole === 'host') {
    autoPlayNext();
  }
}

async function previousTrack() {
  if (!player) return;
  
  try {
    await player.previousTrack();
  } catch (error) {
    console.error('Error skipping to previous track:', error);
  }
}

async function setVolume(volume) {
  if (!player) return;
  
  try {
    await player.setVolume(volume / 100);
  } catch (error) {
    console.error('Error setting volume:', error);
  }
}

async function autoPlayNext() {
  if (window.userRole !== 'host') {
    console.log('Auto-play denied: User is not host');
    return;
  }
  
  try {
    const response = await fetch('/queue/auto-play', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        device_id: deviceId
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      console.log('Auto-play successful:', data.message);
      showNotification(`🎵 Now playing: ${data.track.track_name}`, 'success');
    } else {
      console.error('Auto-play failed:', data.error);
      if (data.error !== 'Queue is empty') {
        showNotification(`❌ ${data.error}`, 'error');
      }
    }
  } catch (error) {
    console.error('Error in auto-play:', error);
    showNotification('❌ Failed to play next track', 'error');
  }
}

function startProgressTracking() {
  if (progressInterval) clearInterval(progressInterval);
  
  progressInterval = setInterval(async () => {
    if (!player) return;
    
    try {
      const state = await player.getCurrentState();
      if (state && !state.paused) {
        updateProgress(state.position, state.track_window.current_track.duration_ms);
      }
    } catch (error) {
      console.error('Error getting player state:', error);
    }
  }, 1000);
}

function stopProgressTracking() {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
}

function startTrackEndDetection() {
  if (trackEndInterval) clearInterval(trackEndInterval);
  
  trackEndInterval = setInterval(async () => {
    if (!player) return;
    
    try {
      const state = await player.getCurrentState();
      if (state && !state.paused) {
        const remaining = state.track_window.current_track.duration_ms - state.position;
        
        if (remaining < 2000) {
          console.log('Track ending soon, preparing next track');
          stopTrackEndDetection();
          
          setTimeout(() => {
            autoPlayNext();
          }, remaining + 500);
        }
      }
    } catch (error) {
      console.error('Error in track end detection:', error);
    }
  }, 5000);
}

function stopTrackEndDetection() {
  if (trackEndInterval) {
    clearInterval(trackEndInterval);
    trackEndInterval = null;
  }
}

async function playTrackFromQueue(trackUri) {
  if (!accessToken || !deviceId) {
    alert('Spotify player not connected');
    return;
  }

  // Find the track name from the queue
  const trackElement = document.querySelector(`li[data-track-uri="${trackUri}"]`);
  let trackName = trackUri.split(':').pop(); // fallback
  
  if (trackElement) {
    const trackNameSpan = trackElement.querySelector('span:first-child');
    if (trackNameSpan) {
      trackName = trackNameSpan.textContent.trim();
    }
  }

  try {
    const response = await fetch('/playback/play', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        track_uri: trackUri,
        track_name: trackName,
        device_id: deviceId 
      })
    });

    if (!response.ok) {
      const error = await response.json();
      console.error('Error playing track:', error);
      
      // Provide more specific error messages
      if (response.status === 404) {
        alert('No active device found. Make sure Spotify is open and try refreshing the page.');
      } else if (error.error && error.error.includes('Premium')) {
        alert('Spotify Premium is required for web playback. Please upgrade your account.');
      } else {
        alert(error.error || 'Failed to play track');
      }
    } else {
      console.log('Successfully started playback');
      
      // DON'T remove the track immediately - let it stay in queue while playing
      // The track will be removed when it finishes playing or when skipped
    }
  } catch (error) {
    console.error('Error playing track:', error);
    alert('Network error. Please check your connection and try again.');
  }
}

// Remove track from queue after it's played
async function removeTrackFromQueue(trackUri) {
  try {
    const response = await fetch(`/queue/remove/${encodeURIComponent(trackUri)}`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      console.log('Track removed from queue:', trackUri);
    } else {
      console.log('Failed to remove track from queue:', trackUri);
    }
  } catch (error) {
    console.error('Error removing track from queue:', error);
  }
}

// Export functions
window.initializeSpotifyPlayer = initializeSpotifyPlayer;
window.togglePlayback = togglePlayback;
window.nextTrack = nextTrack;
window.previousTrack = previousTrack;
window.setVolume = setVolume;
window.autoPlayNext = autoPlayNext;
window.playTrackFromQueue = playTrackFromQueue;
window.removeTrackFromQueue = removeTrackFromQueue;
