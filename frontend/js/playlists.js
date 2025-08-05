// Playlist Management
let userPlaylists = [];

async function loadCustomPlaylists() {
  console.log('loadCustomPlaylists called, userRole:', window.userRole);
  
  const createBtn = document.getElementById('create-playlist-btn');
  if (createBtn) {
    if (window.userRole === 'host') {
      createBtn.style.display = 'inline-block';
      console.log('Create playlist button shown for host');
    } else {
      createBtn.style.display = 'none';
      console.log('Create playlist button hidden for non-host');
    }
  }
  
  if (window.userRole !== 'host') {
    console.log('Not a host, skipping playlist loading');
    return;
  }
  
  try {
    const response = await fetch('/custom_playlists/');
    const data = await response.json();
    
    if (response.ok) {
      userPlaylists = data.playlists || [];
      renderCustomPlaylists();
      console.log('Custom playlists loaded:', userPlaylists.length);
    } else {
      console.error('Failed to load custom playlists:', data.error);
      if (createBtn) {
        createBtn.style.display = 'inline-block';
      }
    }
  } catch (error) {
    console.error('Error loading custom playlists:', error);
    if (createBtn) {
      createBtn.style.display = 'inline-block';
    }
  }
}

// Initialize playlist UI (ensure button visibility)
function initializePlaylistUI() {
  console.log('Initializing playlist UI, userRole:', window.userRole);
  
  const createBtn = document.getElementById('create-playlist-btn');
  if (createBtn) {
    if (window.userRole === 'host') {
      createBtn.style.display = 'inline-block';
      console.log('Create playlist button shown for host');
    } else {
      createBtn.style.display = 'none';
      console.log('Create playlist button hidden for non-host');
    }
  } else {
    console.log('Create playlist button not found in DOM');
  }
}

function renderCustomPlaylists() {
  const playlistList = document.getElementById('custom-playlist-list');
  if (!playlistList) return;
  
  playlistList.innerHTML = '';
  
  if (userPlaylists.length === 0) {
    playlistList.innerHTML = PlaylistTemplates.getEmptyPlaylistTemplate();
    return;
  }
  
  userPlaylists.forEach(playlist => {
    const li = document.createElement('li');
    li.className = 'playlist-item';
    li.innerHTML = PlaylistTemplates.getPlaylistItemTemplate(playlist);
    playlistList.appendChild(li);
  });
}

function showCreatePlaylistModal() {
  const modal = createPlaylistModal();
  document.body.appendChild(modal);
}

function showAddToPlaylistModal(trackUri, trackName, trackArtist, trackAlbum, trackDuration) {
  const modal = createAddToPlaylistModal(trackUri, trackName, trackArtist, trackAlbum, trackDuration);
  document.body.appendChild(modal);
}

function showEditPlaylistModal(playlistId, playlistName, playlistDescription, originalName) {
  const modal = createEditPlaylistModal(playlistId, playlistName, playlistDescription);
  document.body.appendChild(modal);
}

// Create playlist modal HTML
function createPlaylistModal() {
  const modal = document.createElement('div');
  modal.innerHTML = PlaylistTemplates.getModalOverlayTemplate('create-playlist-modal', 
    PlaylistTemplates.getCreatePlaylistModalTemplate());
  
  modal.querySelector('#create-playlist-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('playlist-name-input').value.trim();
    const description = document.getElementById('playlist-description-input').value.trim();
    
    if (!name) {
      alert('Please enter a playlist name');
      return;
    }
    
    try {
      const response = await fetch('/custom_playlists/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: name,
          description: description
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        showNotification(`✅ Playlist "${name}" created successfully!`, 'success');
        closeModal('create-playlist-modal');
        loadCustomPlaylists();
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error('Error creating playlist:', error);
      alert('Failed to create playlist. Please try again.');
    }
  });
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeModal('create-playlist-modal');
    }
  });
  
  return modal;
}

function createAddToPlaylistModal(trackUri, trackName, trackArtist, trackAlbum, trackDuration) {
  const modal = document.createElement('div');
  
  let playlistOptions = '';
  if (userPlaylists.length === 0) {
    playlistOptions = '<option value="">No playlists available</option>';
  } else {
    playlistOptions = '<option value="">Choose a playlist...</option>';
    userPlaylists.forEach(playlist => {
      playlistOptions += `<option value="${playlist.id}">${playlist.name} (${playlist.track_count} tracks)</option>`;
    });
  }
  
  modal.innerHTML = PlaylistTemplates.getModalOverlayTemplate('add-to-playlist-modal',
    PlaylistTemplates.getAddToPlaylistModalTemplate(trackName, trackArtist, trackAlbum, playlistOptions));
  
  modal.querySelector('#create-new-playlist-btn').addEventListener('click', () => {
    const section = modal.querySelector('#new-playlist-section');
    const isVisible = section.style.display !== 'none';
    section.style.display = isVisible ? 'none' : 'block';
    
    const btn = modal.querySelector('#create-new-playlist-btn');
    btn.textContent = isVisible ? '+ Create New Playlist' : '- Cancel New Playlist';
    btn.style.backgroundColor = isVisible ? '#9b59b6' : '#e74c3c';
  });
  
  modal.querySelector('#add-to-playlist-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const selectedPlaylistId = document.getElementById('playlist-select').value;
    const newPlaylistName = document.getElementById('new-playlist-name').value.trim();
    const newPlaylistDesc = document.getElementById('new-playlist-desc').value.trim();
    
    let playlistId = selectedPlaylistId;
    
    if (!selectedPlaylistId && newPlaylistName) {
      try {
        const createResponse = await fetch('/custom_playlists/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            name: newPlaylistName,
            description: newPlaylistDesc
          })
        });
        
        const createData = await createResponse.json();
        
        if (createResponse.ok) {
          playlistId = createData.playlist.id;
          showNotification(`✅ Playlist "${newPlaylistName}" created!`, 'success');
        } else {
          alert(`Error creating playlist: ${createData.error}`);
          return;
        }
      } catch (error) {
        console.error('Error creating playlist:', error);
        alert('Failed to create playlist. Please try again.');
        return;
      }
    }
    
    if (!playlistId) {
      alert('Please select a playlist or create a new one');
      return;
    }
    
    try {
      const response = await fetch(`/custom_playlists/${playlistId}/tracks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          track_uri: trackUri,
          track_name: trackName,
          track_artist: trackArtist,
          track_album: trackAlbum,
          track_duration: trackDuration
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        showNotification(`✅ Track added to playlist successfully!`, 'success');
        closeModal('add-to-playlist-modal');
        loadCustomPlaylists();
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error('Error adding track to playlist:', error);
      alert('Failed to add track to playlist. Please try again.');
    }
  });
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeModal('add-to-playlist-modal');
    }
  });
  
  return modal;
}

function createEditPlaylistModal(playlistId, playlistName, playlistDescription) {
  const modal = document.createElement('div');
  modal.innerHTML = PlaylistTemplates.getModalOverlayTemplate('edit-playlist-modal',
    PlaylistTemplates.getEditPlaylistModalTemplate(playlistName, playlistDescription));
  
  // Handle form submission
  modal.querySelector('#edit-playlist-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('edit-playlist-name-input').value.trim();
    const description = document.getElementById('edit-playlist-description-input').value.trim();
    
    if (!name) {
      alert('Please enter a playlist name');
      return;
    }
    
    try {
      const response = await fetch(`/custom_playlists/${playlistId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: name,
          description: description
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        showNotification(`✅ Playlist updated successfully!`, 'success');
        closeModal('edit-playlist-modal');
        loadCustomPlaylists();
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error('Error updating playlist:', error);
      alert('Failed to update playlist. Please try again.');
    }
  });
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeModal('edit-playlist-modal');
    }
  });
  
  return modal;
}

async function viewPlaylistTracks(playlistId, playlistName) {
  try {
    const response = await fetch(`/custom_playlists/${playlistId}`);
    const data = await response.json();
    
    if (response.ok) {
      showPlaylistTracksModal(data.playlist, data.tracks);
    } else {
      alert(`Error: ${data.error}`);
    }
  } catch (error) {
    console.error('Error loading playlist tracks:', error);
    alert('Failed to load playlist tracks. Please try again.');
  }
}

function showPlaylistTracksModal(playlist, tracks) {
  const modal = document.createElement('div');
  modal.innerHTML = PlaylistTemplates.getModalOverlayTemplate('playlist-tracks-modal',
    PlaylistTemplates.getPlaylistTracksModalTemplate(playlist, tracks));
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeModal('playlist-tracks-modal');
    }
  });
  
  document.body.appendChild(modal);
}

async function removeTrackFromPlaylist(playlistId, trackId, trackName, buttonElement) {
  if (!confirm(`Are you sure you want to remove "${trackName}" from this playlist?`)) {
    return;
  }
  
  try {
    const response = await fetch(`/custom_playlists/${playlistId}/tracks/${trackId}`, {
      method: 'DELETE'
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showNotification(`✅ Track removed from playlist`, 'success');
      const trackElement = buttonElement.closest('div');
      trackElement.remove();
      loadCustomPlaylists();
    } else {
      alert(`Error: ${data.error}`);
    }
  } catch (error) {
    console.error('Error removing track from playlist:', error);
    alert('Failed to remove track from playlist. Please try again.');
  }
}

async function deletePlaylist(playlistId, playlistName, event) {
  event.stopPropagation();
  
  if (!confirm(`Are you sure you want to delete the playlist "${playlistName}"?\n\nThis will also remove all tracks from the playlist. This action cannot be undone.`)) {
    return;
  }
  
  try {
    const response = await fetch(`/custom_playlists/${playlistId}`, {
      method: 'DELETE'
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showNotification(`✅ Playlist "${playlistName}" deleted successfully`, 'success');
      loadCustomPlaylists();
    } else {
      alert(`Error: ${data.error}`);
    }
  } catch (error) {
    console.error('Error deleting playlist:', error);
    alert('Failed to delete playlist. Please try again.');
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.remove();
  }
}

// Exports
window.initializePlaylistUI = initializePlaylistUI;
window.loadCustomPlaylists = loadCustomPlaylists;
window.showCreatePlaylistModal = showCreatePlaylistModal;
window.showAddToPlaylistModal = showAddToPlaylistModal;
window.showEditPlaylistModal = showEditPlaylistModal;
window.viewPlaylistTracks = viewPlaylistTracks;
window.removeTrackFromPlaylist = removeTrackFromPlaylist;
window.deletePlaylist = deletePlaylist;
window.closeModal = closeModal;

initializePlaylistUI();
