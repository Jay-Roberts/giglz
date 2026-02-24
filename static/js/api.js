// static/js/api.js
// Giglz API client - shared across modules

window.GiglzAPI = (function() {
    'use strict';

    /**
     * POST JSON to an endpoint.
     * @param {string} path - API path (e.g., '/api/love-track')
     * @param {object} data - JSON body
     * @returns {Promise<object>} - Parsed JSON response
     * @throws {Error} - On non-2xx response
     */
    async function postJSON(path, data) {
        const response = await fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.error || `Request failed: ${response.status}`);
        }
        return response.json();
    }

    /**
     * GET JSON from an endpoint.
     * @param {string} path - API path
     * @returns {Promise<object>} - Parsed JSON response
     * @throws {Error} - On non-2xx response
     */
    async function getJSON(path) {
        const response = await fetch(path);
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.error || `Request failed: ${response.status}`);
        }
        return response.json();
    }

    // Public API
    return {
        // Auth
        getSpotifyToken: function() {
            return getJSON('/api/spotify-token');
        },

        // Player state (for mobile polling)
        getNowPlaying: function() {
            return getJSON('/api/now-playing');
        },

        // Track love/unlove
        loveTrack: function(uri, name, artist) {
            return postJSON('/api/love-track', { uri, name, artist });
        },

        unloveTrack: function(uri) {
            return postJSON('/api/unlove-track', { uri });
        },

        getTrackStatus: function(uri) {
            return getJSON('/api/track/' + encodeURIComponent(uri) + '/status');
        },

        // Scout Gig - hot-swap Now Scouting playlist
        scoutGig: function(trackUri) {
            return postJSON('/api/scout-gig', { track_uri: trackUri });
        },
    };
})();
