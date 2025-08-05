/**
 * Spotify Player Module
 */

let player = null;
let deviceId = null;
let accessToken = null;

async function initializeSpotifyPlayer() {
  console.log('=== SPOTIFY PLAYER INIT DEBUG ===');
  console.log('User role:', window.userRole);
  console.log('Spotify SDK loaded:', !!window.Spotify);
  console.log('==================================');

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
  });
  
  player.addListener('not_ready', ({ device_id }) => {
    console.log('Spotify player not ready with Device ID:', device_id);
  });
  
  player.addListener('player_state_changed', (state) => {
    if (!state) return;
    console.log('Player state changed:', state);
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
  // For now, this will just trigger the Spotify embed when called from queue
  console.log('Toggle playback called');
}

async function nextTrack() {
  if (window.userRole === 'host') {
    autoPlayNext();
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
      // Auto-play the track via Spotify embed
      if (data.track && data.track.track_uri) {
        playTrackFromQueue(data.track.track_uri);
      }
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

async function playTrackFromQueue(trackUri) {
  console.log('=== PLAY TRACK DEBUG ===');
  console.log('User role:', window.userRole);
  console.log('Track URI:', trackUri);
  console.log('========================');

  if (window.userRole !== 'host') {
    alert('Only hosts can control playback');
    return;
  }

  // Extract Spotify track ID from URI (format: spotify:track:TRACK_ID)
  const trackId = trackUri.split(':')[2];
  if (!trackId) {
    alert('Invalid track format');
    return;
  }

  try {
    // Update the Spotify iframe to play this track
    const spotifyPlayer = document.getElementById('spotify-player');
    const spotifyWrapper = document.getElementById('spotify-embed-wrapper');
    
    if (spotifyPlayer && spotifyWrapper) {
      // Show the Spotify embed
      spotifyWrapper.style.display = 'block';
      
      // Adjust body padding to prevent overlap
      document.body.style.paddingTop = '185px';
      
      // Set the iframe src to play the specific track with autoplay
      const embedUrl = `https://open.spotify.com/embed/track/${trackId}?utm_source=generator&autoplay=1&theme=0&show_cover_art=true`;
      spotifyPlayer.src = embedUrl;
      
      console.log('Updated Spotify embed to play:', trackUri);
      
      // Update our app's UI to show what's playing
      const trackElement = document.querySelector(`li[data-track-uri="${trackUri}"]`);
      let trackName = 'Unknown Track';
      
      if (trackElement) {
        const trackNameSpan = trackElement.querySelector('span:first-child');
        if (trackNameSpan) {
          trackName = trackNameSpan.textContent.trim();
        }
      }
      
      // Broadcast to other users what's playing
      if (typeof socket !== 'undefined') {
        socket.emit('playback_started', {
          track_uri: trackUri,
          track_name: trackName,
          is_playing: true
        });
      }
      
      console.log('Successfully started playback via embed');
      
    } else {
      console.error('Spotify embed elements not found');
      alert('Spotify player not found');
    }
    
  } catch (error) {
    console.error('Error playing track:', error);
    alert('Failed to play track. Please try again.');
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

// Function to hide the Spotify player
function hideSpotifyPlayer() {
  const spotifyWrapper = document.getElementById('spotify-embed-wrapper');
  if (spotifyWrapper) {
    spotifyWrapper.style.display = 'none';
    // Reset body padding when player is hidden
    document.body.style.paddingTop = '20px';
  }
}

// Export functions
window.initializeSpotifyPlayer = initializeSpotifyPlayer;
window.togglePlayback = togglePlayback;
window.nextTrack = nextTrack;
window.autoPlayNext = autoPlayNext;
window.playTrackFromQueue = playTrackFromQueue;
window.removeTrackFromQueue = removeTrackFromQueue;
window.hideSpotifyPlayer = hideSpotifyPlayer;
window.hideSpotifyPlayer = hideSpotifyPlayer;
