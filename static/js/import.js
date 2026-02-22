// static/js/import.js
// SSE import flow for URL imports

window.GiglzImport = (function() {
    'use strict';

    // ---------------------
    // State
    // ---------------------
    let isImporting = false;
    let elements = {};

    // ---------------------
    // Private: DOM
    // ---------------------
    function cacheElements() {
        elements = {
            form: document.getElementById('import-form'),
            btn: document.getElementById('import-btn'),
            btnText: document.getElementById('import-btn-text'),
            spinner: document.getElementById('import-spinner'),
            progressSection: document.getElementById('import-progress'),
            progressCount: document.getElementById('progress-count'),
            progressSpinner: document.getElementById('progress-spinner'),
            importResults: document.getElementById('import-results'),
            savedShowsSection: document.getElementById('saved-shows-section'),
            savedShows: document.getElementById('saved-shows'),
        };
    }

    function setImporting(importing) {
        isImporting = importing;

        if (elements.btn) {
            elements.btn.disabled = importing;
            elements.btn.classList.toggle('opacity-75', importing);
            elements.btn.classList.toggle('cursor-not-allowed', importing);
        }

        if (elements.btnText) {
            elements.btnText.textContent = importing ? 'Importing...' : 'Import from URLs';
        }

        if (elements.spinner) {
            elements.spinner.classList.toggle('hidden', !importing);
        }

        if (elements.progressSpinner) {
            elements.progressSpinner.classList.toggle('hidden', !importing);
        }
    }

    // ---------------------
    // Private: Show Cards
    // ---------------------
    function createShowCard(data) {
        const card = document.createElement('div');
        card.dataset.status = data.status;

        if (data.status === 'SUCCESS' && data.show) {
            card.className = 'bg-gig-card rounded p-4 border border-gig-cyan/20 grooving';
            card.dataset.showId = data.show.id;
            card.innerHTML = `
                <div class="flex justify-between items-start">
                    <div>
                        <h3 class="font-bold text-gig-pink">${escapeHtml(data.show.artists.join(', '))}</h3>
                        <p class="text-sm text-gray-400 mt-1 font-mono">
                            ${escapeHtml(data.show.venue)} <span class="text-gig-cyan/40">//</span> ${escapeHtml(data.show.date)}
                        </p>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="loved-count text-xs bg-gig-pink/20 text-gig-pink px-2 py-1 rounded font-mono hidden flex items-center gap-1">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>
                            <span class="loved-count-num">0</span>
                        </span>
                        <span class="text-xs bg-gig-cyan/20 text-gig-cyan px-2 py-1 rounded font-mono">
                            ${data.show.track_count} trx
                        </span>
                    </div>
                </div>
            `;
        } else if (data.status === 'SKIPPED') {
            card.className = 'bg-gig-card/50 rounded p-3 border border-gray-600/30 text-gray-500 text-sm';
            card.innerHTML = `<span class="font-mono">↩</span> Already imported: ${escapeHtml(truncateUrl(data.url))}`;
        } else if (data.status === 'FAILED') {
            card.className = 'bg-gig-card/50 rounded p-3 border border-gig-pink/30 text-gig-pink text-sm';
            card.innerHTML = `<span class="font-mono">✗</span> ${escapeHtml(data.error || 'Unknown error')}`;
        }

        return card;
    }

    function truncateUrl(url) {
        try {
            const u = new URL(url);
            const path = u.pathname.length > 30 ? u.pathname.slice(0, 30) + '...' : u.pathname;
            return u.hostname + path;
        } catch {
            return url.slice(0, 50);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ---------------------
    // Private: SSE Handling
    // ---------------------
    function handleEvent(data) {
        if (data.type === 'progress') {
            if (elements.progressCount) {
                elements.progressCount.textContent = `${data.index + 1} / ${data.total}`;
            }

            const card = createShowCard(data);
            elements.importResults?.appendChild(card);

        } else if (data.type === 'complete') {
            // Remove grooving animation from success cards
            const successCards = elements.importResults?.querySelectorAll('[data-status="SUCCESS"]');
            successCards?.forEach(card => { card.classList.remove('grooving'); });

            // If savedShowsSection exists, move cards there; otherwise reload page
            if (elements.savedShowsSection && elements.savedShows) {
                if (successCards && successCards.length > 0) {
                    elements.savedShowsSection.classList.remove('hidden');
                    successCards.forEach(card => {
                        elements.savedShows.insertBefore(card, elements.savedShows.firstChild);
                    });
                }
            } else if (data.imported > 0) {
                // Reload to show updated playlist list on home page
                setTimeout(() => window.location.reload(), 1500);
            }
        }
    }

    async function startImport(formData) {
        setImporting(true);

        // Show progress section, clear previous results
        elements.progressSection?.classList.remove('hidden');
        if (elements.importResults) {
            elements.importResults.innerHTML = '';
        }
        if (elements.progressCount) {
            elements.progressCount.textContent = '';
        }

        try {
            const response = await fetch('/import-shows/stream', {
                method: 'POST',
                body: formData,
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();  // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            handleEvent(data);
                        } catch (e) {
                            console.error('Failed to parse SSE data:', e);
                        }
                    }
                }
            }
        } catch (e) {
            console.error('SSE error:', e);
        } finally {
            finishImport();
        }
    }

    function finishImport() {
        setImporting(false);

        // Clear the textarea
        const textarea = elements.form?.querySelector('textarea');
        if (textarea) {
            textarea.value = '';
        }
    }

    // ---------------------
    // Private: Form Handler
    // ---------------------
    function handleSubmit(e) {
        e.preventDefault();

        const formData = new FormData(elements.form);
        const urls = formData.get('urls');

        if (!urls || !urls.trim()) {
            alert('Paste at least one URL.');
            return;
        }

        startImport(formData);
    }

    // ---------------------
    // Public Interface
    // ---------------------
    return {
        /**
         * Initialize import form handling.
         * Call once on pages with the import form.
         */
        init: function() {
            cacheElements();

            if (elements.form) {
                elements.form.addEventListener('submit', handleSubmit);
            }
        },

        /**
         * Check if an import is in progress.
         * Used by beforeunload handler.
         */
        isImporting: function() {
            return isImporting;
        },
    };
})();
