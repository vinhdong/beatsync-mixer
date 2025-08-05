// Playlist HTML Templates

function getCreatePlaylistModalTemplate() {
  return `
    <div style="
      background: white;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      max-width: 400px;
      width: 90%;
    ">
      <h3 style="margin: 0 0 20px 0; color: #333;">Create New Playlist</h3>
      <form id="create-playlist-form">
        <div style="margin-bottom: 15px;">
          <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #555;">Playlist Name:</label>
          <input type="text" id="playlist-name-input" required style="
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            box-sizing: border-box;
          " placeholder="Enter playlist name..." maxlength="100">
        </div>
        <div style="margin-bottom: 20px;">
          <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #555;">Description (optional):</label>
          <textarea id="playlist-description-input" style="
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            resize: vertical;
            min-height: 60px;
            box-sizing: border-box;
          " placeholder="Enter description..." maxlength="500"></textarea>
        </div>
        <div style="display: flex; gap: 10px; justify-content: flex-end;">
          <button type="button" onclick="closeModal('create-playlist-modal')" style="
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
          ">Cancel</button>
          <button type="submit" style="
            background-color: #1db954;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
          ">Create Playlist</button>
        </div>
      </form>
    </div>
  `;
}

function getAddToPlaylistModalTemplate(trackName, trackArtist, trackAlbum, playlistOptions) {
  return `
    <div style="
      background: white;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      max-width: 450px;
      width: 90%;
    ">
      <h3 style="margin: 0 0 20px 0; color: #333;">Add Track to Playlist</h3>
      
      <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; color: #333;">
        <div style="font-weight: bold; margin-bottom: 5px; color: #333;">${trackName}</div>
        <div style="color: #666; font-size: 0.9em;">${trackArtist}</div>
        ${trackAlbum ? `<div style="color: #888; font-size: 0.8em;">${trackAlbum}</div>` : ''}
      </div>
      
      <form id="add-to-playlist-form">
        <div style="margin-bottom: 15px;">
          <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #555;">Select Playlist:</label>
          <select id="playlist-select" style="
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            box-sizing: border-box;
          ">
            ${playlistOptions}
          </select>
        </div>
        
        <div style="margin-bottom: 20px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="color: #666;">or</span>
            <button type="button" id="create-new-playlist-btn" style="
              background-color: #9b59b6;
              color: white;
              border: none;
              padding: 8px 16px;
              border-radius: 6px;
              cursor: pointer;
              font-size: 12px;
            ">+ Create New Playlist</button>
          </div>
        </div>
        
        <div id="new-playlist-section" style="display: none; margin-bottom: 20px; padding: 15px; background: #f0f0f0; border-radius: 8px;">
          <div style="margin-bottom: 10px;">
            <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #555;">New Playlist Name:</label>
            <input type="text" id="new-playlist-name" style="
              width: 100%;
              padding: 8px;
              border: 2px solid #ddd;
              border-radius: 4px;
              font-size: 14px;
              box-sizing: border-box;
            " placeholder="Enter new playlist name..." maxlength="100">
          </div>
          <div>
            <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #555;">Description (optional):</label>
            <input type="text" id="new-playlist-desc" style="
              width: 100%;
              padding: 8px;
              border: 2px solid #ddd;
              border-radius: 4px;
              font-size: 14px;
              box-sizing: border-box;
            " placeholder="Enter description..." maxlength="200">
          </div>
        </div>
        
        <div style="display: flex; gap: 10px; justify-content: flex-end;">
          <button type="button" onclick="closeModal('add-to-playlist-modal')" style="
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
          ">Cancel</button>
          <button type="submit" style="
            background-color: #1db954;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
          ">Add to Playlist</button>
        </div>
      </form>
    </div>
  `;
}

function getEditPlaylistModalTemplate(playlistName, playlistDescription) {
  return `
    <div style="
      background: white;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      max-width: 400px;
      width: 90%;
    ">
      <h3 style="margin: 0 0 20px 0; color: #333;">Edit Playlist</h3>
      <form id="edit-playlist-form">
        <div style="margin-bottom: 15px;">
          <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #555;">Playlist Name:</label>
          <input type="text" id="edit-playlist-name-input" required value="${playlistName}" style="
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            box-sizing: border-box;
          " maxlength="100">
        </div>
        <div style="margin-bottom: 20px;">
          <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #555;">Description:</label>
          <textarea id="edit-playlist-description-input" style="
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            resize: vertical;
            min-height: 60px;
            box-sizing: border-box;
          " maxlength="500">${playlistDescription}</textarea>
        </div>
        <div style="display: flex; gap: 10px; justify-content: flex-end;">
          <button type="button" onclick="closeModal('edit-playlist-modal')" style="
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
          ">Cancel</button>
          <button type="submit" style="
            background-color: #f39c12;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
          ">Update Playlist</button>
        </div>
      </form>
    </div>
  `;
}

function getPlaylistTracksModalTemplate(playlist, tracks) {
  const tracksHtml = tracks.length === 0 
    ? getNoTracksTemplate()
    : tracks.map(track => getTrackItemTemplate(track, playlist.id)).join('');
    
  return `
    <div style="
      background: white;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      max-width: 600px;
      width: 90%;
      max-height: 80vh;
      overflow-y: auto;
    ">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3 style="margin: 0; color: #333;">${playlist.name}</h3>
        <button onclick="closeModal('playlist-tracks-modal')" style="
          background: none;
          border: none;
          font-size: 20px;
          cursor: pointer;
          color: #999;
        ">✕</button>
      </div>
      
      ${playlist.description ? `<div style="color: #666; margin-bottom: 20px; font-style: italic;">${playlist.description}</div>` : ''}
      
      <div style="margin-bottom: 15px; color: #888; font-size: 0.9em;">
        ${tracks.length} track${tracks.length !== 1 ? 's' : ''}
      </div>
      
      <div id="playlist-tracks-list">
        ${tracksHtml}
      </div>
    </div>
  `;
}

function getPlaylistItemTemplate(playlist) {
  return `
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #f5f5f5; border-radius: 6px; margin-bottom: 8px;">
      <div>
        <div style="font-weight: bold; margin-bottom: 4px;">${playlist.name}</div>
        <div style="font-size: 0.9em; color: #666;">${playlist.track_count} tracks</div>
        ${playlist.description ? `<div style="font-size: 0.8em; color: #888; margin-top: 2px;">${playlist.description}</div>` : ''}
      </div>
      <div style="display: flex; gap: 8px;">
        <button onclick="viewPlaylistTracks(${playlist.id}, '${playlist.name.replace(/'/g, "\\'")}')" style="background-color: #3498db; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">👁️ View</button>
        <button onclick="showEditPlaylistModal(${playlist.id}, '${playlist.name.replace(/'/g, "\\'")}', '${(playlist.description || '').replace(/'/g, "\\'")}', '${playlist.name.replace(/'/g, "\\'")}Backup')" style="background-color: #f39c12; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">✏️ Edit</button>
        <button onclick="deletePlaylist(${playlist.id}, '${playlist.name.replace(/'/g, "\\'")}', event)" style="background-color: #e74c3c; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">🗑️ Delete</button>
      </div>
    </div>
  `;
}

function getTrackItemTemplate(track, playlistId) {
  return `
    <div style="
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px;
      background: #f8f9fa;
      border-radius: 6px;
      margin-bottom: 8px;
    ">
      <div>
        <div style="font-weight: bold; margin-bottom: 4px;">${track.track_name}</div>
        <div style="color: #666; font-size: 0.9em;">${track.track_artist}</div>
        ${track.track_album ? `<div style="color: #888; font-size: 0.8em;">${track.track_album}</div>` : ''}
      </div>
      <button onclick="removeTrackFromPlaylist(${playlistId}, ${track.id}, '${track.track_name.replace(/'/g, "\\'")}', this)" style="
        background-color: #e74c3c;
        color: white;
        border: none;
        padding: 6px 10px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      ">🗑️ Remove</button>
    </div>
  `;
}

function getModalOverlayTemplate(modalId, content) {
  return `
    <div id="${modalId}" style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 2000;
    ">
      ${content}
    </div>
  `;
}

function getEmptyPlaylistTemplate() {
  return `
    <li style="color: #666; font-style: italic; padding: 10px;">
      No custom playlists yet. Create your first one!
    </li>
  `;
}

function getNoTracksTemplate() {
  return `
    <div style="text-align: center; color: #666; padding: 20px; font-style: italic;">
      No tracks in this playlist yet.
    </div>
  `;
}

window.PlaylistTemplates = {
  getCreatePlaylistModalTemplate,
  getAddToPlaylistModalTemplate,
  getEditPlaylistModalTemplate,
  getPlaylistTracksModalTemplate,
  getPlaylistItemTemplate,
  getTrackItemTemplate,
  getModalOverlayTemplate,
  getEmptyPlaylistTemplate,
  getNoTracksTemplate
};
