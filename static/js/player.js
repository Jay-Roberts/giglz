// static/js/player.js
// Spotify player - SDK for desktop, polling for mobile
// Includes both mini player bar and expanded player view

window.GiglzPlayer = (function() {
    'use strict';

    // ---------------------
    // State
    // ---------------------
    let player = null;           // Spotify SDK player instance
    let _deviceId = null;        // SDK device ID (unused but kept for debugging)
    let currentTrack = null;     // { uri, name, artist, albumArt }
    let isPlaying = false;
    let isLoved = false;
    let isScouted = true;        // false = track not from scouted show (broken heart)
    let isShuffled = false;
    let repeatMode = 'off';      // 'off' | 'context' | 'track'
    let usePolling = false;      // true if SDK unavailable
    let pollInterval = null;     // polling timer ID

    // ---------------------
    // DOM Elements
    // ---------------------
    let el = {};  // Populated in init()

    // ---------------------
    // Private: DOM Caching
    // ---------------------
    function cacheElements() {
        el = {
            // Player bar (mini)
            playerBar: document.getElementById('player-bar'),
            albumArt: document.getElementById('player-album-art'),
            albumLoading: document.getElementById('album-loading'),
            trackName: document.getElementById('player-track-name'),
            artistName: document.getElementById('player-artist-name'),
            showContext: document.getElementById('player-show-context'),
            btnPlay: document.getElementById('btn-play'),
            btnPrev: document.getElementById('btn-prev'),
            btnNext: document.getElementById('btn-next'),
            btnLove: document.getElementById('btn-love'),
            btnShuffle: document.getElementById('btn-shuffle'),
            btnRepeat: document.getElementById('btn-repeat'),
            btnExpand: document.getElementById('btn-expand'),
            iconPlay: document.getElementById('icon-play'),
            iconPause: document.getElementById('icon-pause'),
            iconHeartEmpty: document.getElementById('icon-heart-empty'),
            iconHeartFilled: document.getElementById('icon-heart-filled'),
            iconHeartBroken: document.getElementById('icon-heart-broken'),
            shuffleDot: document.getElementById('shuffle-dot'),
            repeatDot: document.getElementById('repeat-dot'),
            repeatOne: document.getElementById('repeat-one'),

            // Expanded player
            playerDim: document.getElementById('player-dim'),
            playerExpanded: document.getElementById('player-expanded'),
            btnCollapse: document.getElementById('btn-collapse'),
            expandedAlbumArt: document.getElementById('expanded-album-art'),
            expandedTrackName: document.getElementById('expanded-track-name'),
            expandedArtistName: document.getElementById('expanded-artist-name'),
            expandedBtnPlay: document.getElementById('expanded-btn-play'),
            expandedBtnPrev: document.getElementById('expanded-btn-prev'),
            expandedBtnNext: document.getElementById('expanded-btn-next'),
            expandedIconPlay: document.getElementById('expanded-icon-play'),
            expandedIconPause: document.getElementById('expanded-icon-pause'),
            btnLoveBig: document.getElementById('btn-love-big'),
            bigHeartEmpty: document.getElementById('big-heart-empty'),
            bigHeartFilled: document.getElementById('big-heart-filled'),
            bigHeartBroken: document.getElementById('big-heart-broken'),
            loveFeedback: document.getElementById('love-feedback'),
            notScoutedMsg: document.getElementById('not-scouted-msg'),
            btnScoutGig: document.getElementById('btn-scout-gig'),
        };
    }

    // ---------------------
    // Private: Player Bar
    // ---------------------
    function showPlayerBar() {
        if (el.playerBar) {
            el.playerBar.classList.remove('hidden');
            document.getElementById('page-body')?.classList.add('pb-20');
        }
    }

    function updateTrackDisplay(track, showContext = null) {
        if (!track) {
            if (el.trackName) el.trackName.textContent = usePolling ? 'Nothing playing' : 'Connect Spotify to Giglz Player';
            if (el.artistName) el.artistName.textContent = '';
            if (el.albumArt) el.albumArt.src = '';
            el.albumLoading?.classList.remove('hidden');
            el.showContext?.classList.add('hidden');
            return;
        }

        if (el.trackName) el.trackName.textContent = track.name;
        if (el.artistName) el.artistName.textContent = track.artist;

        if (track.albumArt) {
            el.albumLoading?.classList.add('hidden');
            if (el.albumArt) el.albumArt.src = track.albumArt;
        }

        // Show context (venue + date) if available
        if (showContext && showContext.venue && el.showContext) {
            el.showContext.textContent = `${showContext.venue} · ${showContext.date}`;
            el.showContext.classList.remove('hidden');
        } else {
            el.showContext?.classList.add('hidden');
        }

        // Sync expanded player if visible
        if (isExpandedVisible()) {
            syncExpandedPlayer();
        }
    }

    function updatePlayPauseButton(paused) {
        // Mini player
        el.iconPlay?.classList.toggle('hidden', !paused);
        el.iconPause?.classList.toggle('hidden', paused);
        // Expanded player
        el.expandedIconPlay?.classList.toggle('hidden', !paused);
        el.expandedIconPause?.classList.toggle('hidden', paused);
    }

    function updateLoveButton(loved, scouted = true) {
        isLoved = loved;
        isScouted = scouted;

        if (!scouted) {
            // Show broken heart, hide others
            el.iconHeartEmpty?.classList.add('hidden');
            el.iconHeartFilled?.classList.add('hidden');
            el.iconHeartBroken?.classList.remove('hidden');
            el.bigHeartEmpty?.classList.add('hidden');
            el.bigHeartFilled?.classList.add('hidden');
            el.bigHeartBroken?.classList.remove('hidden');
            el.notScoutedMsg?.classList.remove('hidden');
            // Disable love button
            el.btnLove?.classList.add('cursor-not-allowed', 'opacity-50');
            el.btnLoveBig?.classList.add('cursor-not-allowed', 'opacity-50');
            // Hide scout gig button
            el.btnScoutGig?.classList.add('hidden');
        } else {
            // Normal heart states
            el.iconHeartBroken?.classList.add('hidden');
            el.bigHeartBroken?.classList.add('hidden');
            el.notScoutedMsg?.classList.add('hidden');
            el.btnLove?.classList.remove('cursor-not-allowed', 'opacity-50');
            el.btnLoveBig?.classList.remove('cursor-not-allowed', 'opacity-50');
            // Mini player
            el.iconHeartEmpty?.classList.toggle('hidden', loved);
            el.iconHeartFilled?.classList.toggle('hidden', !loved);
            // Expanded player
            el.bigHeartEmpty?.classList.toggle('hidden', loved);
            el.bigHeartFilled?.classList.toggle('hidden', !loved);
            // Show scout gig button only when loved
            el.btnScoutGig?.classList.toggle('hidden', !loved);
        }
    }

    function updateShuffleButton(shuffled) {
        isShuffled = shuffled;
        el.btnShuffle?.classList.toggle('text-gig-cyan', shuffled);
        el.btnShuffle?.classList.toggle('text-gray-400', !shuffled);
        el.shuffleDot?.classList.toggle('hidden', !shuffled);
    }

    function updateRepeatButton(mode) {
        repeatMode = mode;
        const active = mode !== 'off';
        el.btnRepeat?.classList.toggle('text-gig-cyan', active);
        el.btnRepeat?.classList.toggle('text-gray-400', !active);
        el.repeatDot?.classList.toggle('hidden', !active);
        el.repeatOne?.classList.toggle('hidden', mode !== 'track');
    }

    // ---------------------
    // Private: Expanded Player
    // ---------------------
    function isExpandedVisible() {
        return el.playerExpanded && !el.playerExpanded.classList.contains('translate-y-full');
    }

    function showExpanded() {
        el.playerDim?.classList.remove('hidden');
        el.playerExpanded?.classList.remove('translate-y-full');
        syncExpandedPlayer();
    }

    function hideExpanded() {
        el.playerExpanded?.classList.add('translate-y-full');
        el.playerDim?.classList.add('hidden');
    }

    function syncExpandedPlayer() {
        if (el.expandedAlbumArt && el.albumArt) {
            el.expandedAlbumArt.src = el.albumArt.src;
        }
        if (el.expandedTrackName && el.trackName) {
            el.expandedTrackName.textContent = el.trackName.textContent;
        }
        if (el.expandedArtistName && el.artistName) {
            el.expandedArtistName.textContent = el.artistName.textContent;
        }
        el.expandedIconPlay?.classList.toggle('hidden', isPlaying);
        el.expandedIconPause?.classList.toggle('hidden', !isPlaying);
    }

    // Emoticon animation: :) → ;) → ;x → gone
    function playLoveAnimation() {
        if (!el.loveFeedback) return;
        const sequence = [': )', '; )', '; x', ''];
        let i = 0;
        el.loveFeedback.textContent = sequence[i];

        const interval = setInterval(() => {
            i++;
            if (i >= sequence.length) {
                clearInterval(interval);
                return;
            }
            el.loveFeedback.textContent = sequence[i];
        }, 300);
    }

    // ---------------------
    // Private: Love/Unlove
    // ---------------------
    /**
     * Check track status (loved + scouted).
     * @returns {{ loved: boolean, scouted: boolean }}
     */
    async function checkTrackStatus(uri) {
        if (!uri) return { loved: false, scouted: false };
        try {
            const data = await GiglzAPI.getTrackStatus(uri);
            return {
                loved: data.loved,
                scouted: data.shows && data.shows.length > 0,
            };
        } catch (e) {
            console.error('Failed to check track status:', e);
            return { loved: false, scouted: false };
        }
    }

    async function toggleLove() {
        if (!currentTrack?.uri) return;
        if (!isScouted) return;  // Can't love non-scouted tracks

        try {
            const result = isLoved
                ? await GiglzAPI.unloveTrack(currentTrack.uri)
                : await GiglzAPI.loveTrack(currentTrack.uri, currentTrack.name, currentTrack.artist);

            updateLoveButton(result.loved, true);
            updateShowCards(result.shows_updated);
        } catch (e) {
            console.error('Failed to toggle love:', e);
        }
    }

    async function handleBigHeartClick() {
        if (!currentTrack?.uri) return;
        await toggleLove();
        if (isLoved) {
            playLoveAnimation();
        }
    }

    async function handleScoutGig() {
        if (!currentTrack?.uri || !isScouted) return;

        // Disable button while processing
        if (el.btnScoutGig) {
            el.btnScoutGig.disabled = true;
            el.btnScoutGig.textContent = 'Scouting...';
        }

        try {
            const result = await GiglzAPI.scoutGig(currentTrack.uri);

            if (result.success) {
                // Show success feedback
                if (el.btnScoutGig) {
                    const artists = result.show.artists.slice(0, 2).join(', ');
                    el.btnScoutGig.textContent = `Now scouting ${artists}`;
                    el.btnScoutGig.classList.remove('border-gig-cyan/50', 'text-gig-cyan', 'bg-gig-cyan/20');
                    el.btnScoutGig.classList.add('border-gig-pink/50', 'text-gig-pink', 'bg-gig-pink/20');
                }

                // Reset after delay
                setTimeout(() => {
                    if (el.btnScoutGig) {
                        el.btnScoutGig.innerHTML = el.btnScoutGig.dataset.originalText || 'Scout this gig &rarr;';
                        el.btnScoutGig.classList.add('border-gig-cyan/50', 'text-gig-cyan', 'bg-gig-cyan/20');
                        el.btnScoutGig.classList.remove('border-gig-pink/50', 'text-gig-pink', 'bg-gig-pink/20');
                        el.btnScoutGig.disabled = false;
                    }
                }, 3000);
            }
        } catch (e) {
            console.error('Scout gig failed:', e);
            if (el.btnScoutGig) {
                el.btnScoutGig.textContent = 'Failed - try again';
                el.btnScoutGig.disabled = false;
                setTimeout(() => {
                    el.btnScoutGig.innerHTML = el.btnScoutGig.dataset.originalText || 'Scout this gig &rarr;';
                }, 2000);
            }
        }
    }

    function updateShowCards(showsUpdated) {
        if (!showsUpdated) return;
        for (const update of showsUpdated) {
            const card = document.querySelector(`[data-show-id="${update.id}"]`);
            if (!card) continue;

            const lovedCount = card.querySelector('.loved-count');
            const lovedCountNum = card.querySelector('.loved-count-num');
            if (!lovedCount || !lovedCountNum) continue;

            lovedCountNum.textContent = update.loved_count;
            lovedCount.classList.toggle('hidden', update.loved_count === 0);
        }
    }

    // ---------------------
    // Private: Shuffle/Repeat
    // ---------------------
    async function setShuffle(state) {
        try {
            const token = (await GiglzAPI.getSpotifyToken()).access_token;
            const response = await fetch(
                `https://api.spotify.com/v1/me/player/shuffle?state=${state}`,
                { method: 'PUT', headers: { Authorization: `Bearer ${token}` } }
            );
            if (response.ok || response.status === 204) {
                updateShuffleButton(state);
            }
        } catch (e) {
            console.error('Failed to set shuffle:', e);
        }
    }

    async function cycleRepeat() {
        const modes = ['off', 'context', 'track'];
        const nextMode = modes[(modes.indexOf(repeatMode) + 1) % modes.length];

        try {
            const token = (await GiglzAPI.getSpotifyToken()).access_token;
            const response = await fetch(
                `https://api.spotify.com/v1/me/player/repeat?state=${nextMode}`,
                { method: 'PUT', headers: { Authorization: `Bearer ${token}` } }
            );
            if (response.ok || response.status === 204) {
                updateRepeatButton(nextMode);
            }
        } catch (e) {
            console.error('Failed to set repeat:', e);
        }
    }

    // ---------------------
    // Private: SDK Player
    // ---------------------
    async function initSDKPlayer() {
        let token;
        try {
            token = (await GiglzAPI.getSpotifyToken()).access_token;
        } catch (e) {
            console.error('Failed to get token, falling back to polling:', e);
            initPollingPlayer();
            return;
        }

        player = new Spotify.Player({
            name: 'Giglz Player',
            getOAuthToken: cb => cb(token),
            volume: 0.5,
        });

        player.addListener('ready', async ({ device_id }) => {
            console.log('Player ready:', device_id);
            _deviceId = device_id;
            showPlayerBar();
            await setDefaultPlaybackModes();
        });

        player.addListener('not_ready', ({ device_id }) => {
            console.log('Player not ready:', device_id);
        });

        player.addListener('player_state_changed', async (state) => {
            if (!state) {
                isPlaying = false;
                return;
            }

            isPlaying = !state.paused;
            const track = state.track_window.current_track;

            currentTrack = {
                uri: track.uri,
                name: track.name,
                artist: track.artists.map(a => a.name).join(', '),
                albumArt: track.album.images[track.album.images.length - 1]?.url,
            };

            updateTrackDisplay(currentTrack);
            updatePlayPauseButton(state.paused);

            const status = await checkTrackStatus(track.uri);
            updateLoveButton(status.loved, status.scouted);
        });

        player.addListener('initialization_error', ({ message }) => {
            console.error('SDK init error:', message);
            initPollingPlayer();
        });

        player.addListener('authentication_error', ({ message }) => {
            console.error('SDK auth error:', message);
        });

        player.addListener('account_error', ({ message }) => {
            console.error('SDK account error:', message);
        });

        const connected = await player.connect();
        if (!connected) {
            console.error('Player connect failed, falling back to polling');
            initPollingPlayer();
        }
    }

    async function setDefaultPlaybackModes() {
        await setShuffle(true);
        repeatMode = 'off';
        await cycleRepeat();  // Sets to 'context'
    }

    // ---------------------
    // Private: Polling Player
    // ---------------------
    const POLL_INTERVAL_MS = 3000;

    function initPollingPlayer() {
        usePolling = true;
        console.log('Using polling mode for player');
        showPlayerBar();
        hidePlaybackControls();

        pollNowPlaying();
        startPolling();

        // Pause polling when tab hidden, resume when visible
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                stopPolling();
            } else {
                pollNowPlaying();  // Immediate refresh on return
                startPolling();
            }
        });
    }

    function startPolling() {
        if (!pollInterval) {
            pollInterval = setInterval(pollNowPlaying, POLL_INTERVAL_MS);
        }
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    function hidePlaybackControls() {
        // Hide controls that don't work in polling mode
        el.btnPrev?.classList.add('hidden');
        el.btnPlay?.classList.add('hidden');
        el.btnNext?.classList.add('hidden');
        el.btnShuffle?.classList.add('hidden');
        el.btnRepeat?.classList.add('hidden');
        // Expanded player controls
        el.expandedBtnPrev?.classList.add('hidden');
        el.expandedBtnPlay?.classList.add('hidden');
        el.expandedBtnNext?.classList.add('hidden');
    }

    async function pollNowPlaying() {
        try {
            const data = await GiglzAPI.getNowPlaying();

            if (!data.playing) {
                isPlaying = false;
                currentTrack = null;
                updateTrackDisplay(null);
                updatePlayPauseButton(true);
                updateLoveButton(false, true);  // Reset to empty heart
                return;
            }

            isPlaying = data.is_playing;
            currentTrack = {
                uri: data.track_uri,
                name: data.track_name,
                artist: data.artist_name,
                albumArt: data.album_art_url,
            };

            // Build show context if available
            const showContext = data.show_venue ? {
                venue: data.show_venue,
                date: data.show_date,
            } : null;

            updateTrackDisplay(currentTrack, showContext);
            updatePlayPauseButton(!data.is_playing);

            // Check scouted status from API response
            if (!data.is_scouted) {
                updateLoveButton(false, false);  // Broken heart
            } else {
                const status = await checkTrackStatus(data.track_uri);
                updateLoveButton(status.loved, true);
            }
        } catch (e) {
            console.error('Polling failed:', e);
        }
    }

    // ---------------------
    // Private: Touch Gestures
    // ---------------------
    let touchStartY = 0;

    function wireSwipeGestures() {
        if (!el.playerBar) return;

        el.playerBar.addEventListener('touchstart', (e) => {
            touchStartY = e.touches[0].clientY;
        }, { passive: true });

        el.playerBar.addEventListener('touchend', (e) => {
            const deltaY = e.changedTouches[0].clientY - touchStartY;

            // Swipe up = expand player
            if (deltaY < -30) {
                showExpanded();
            }
        }, { passive: true });
    }

    // ---------------------
    // Private: Control Handlers
    // ---------------------
    function wireControls() {
        // Mini player controls
        el.btnPlay?.addEventListener('click', () => {
            if (usePolling) {
                console.log('Playback control not available in polling mode');
            } else {
                player?.togglePlay();
            }
        });
        el.btnPrev?.addEventListener('click', () => {
            if (!usePolling) player?.previousTrack();
        });
        el.btnNext?.addEventListener('click', () => {
            if (!usePolling) player?.nextTrack();
        });
        el.btnLove?.addEventListener('click', toggleLove);
        el.btnShuffle?.addEventListener('click', () => setShuffle(!isShuffled));
        el.btnRepeat?.addEventListener('click', cycleRepeat);
        el.btnExpand?.addEventListener('click', showExpanded);

        // Expanded player controls
        el.btnCollapse?.addEventListener('click', hideExpanded);
        el.expandedBtnPlay?.addEventListener('click', () => {
            if (!usePolling) player?.togglePlay();
        });
        el.expandedBtnPrev?.addEventListener('click', () => {
            if (!usePolling) player?.previousTrack();
        });
        el.expandedBtnNext?.addEventListener('click', () => {
            if (!usePolling) player?.nextTrack();
        });
        el.btnLoveBig?.addEventListener('click', handleBigHeartClick);

        // Scout gig button
        if (el.btnScoutGig) {
            el.btnScoutGig.dataset.originalText = el.btnScoutGig.innerHTML;
            el.btnScoutGig.addEventListener('click', handleScoutGig);
        }

        // Close expanded on Escape or clicking overlay
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isExpandedVisible()) {
                hideExpanded();
            }
        });
        el.playerDim?.addEventListener('click', hideExpanded);
    }

    // ---------------------
    // Private: SDK Detection
    // ---------------------
    function canUseWebPlaybackSDK() {
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        return !isMobile;
    }

    // ---------------------
    // Public Interface
    // ---------------------
    return {
        init: function() {
            cacheElements();
            wireControls();
            wireSwipeGestures();

            if (canUseWebPlaybackSDK()) {
                window.onSpotifyWebPlaybackSDKReady = initSDKPlayer;
            } else {
                initPollingPlayer();
            }
        },

        isPlaying: function() {
            return isPlaying;
        },

        getCurrentTrack: function() {
            return currentTrack;
        },

        destroy: function() {
            stopPolling();
            if (player) {
                player.disconnect();
                player = null;
            }
        },
    };
})();
