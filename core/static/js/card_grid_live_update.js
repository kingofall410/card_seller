function patchCardUpdates(updatedCards) {
    const state = window.CardLiveFeedState;
    if (state.isApplyingServerUpdate || !updatedCards) return; 

    if (!Array.isArray(updatedCards)) updatedCards = [updatedCards];
    const table = $('#card-data-engine').DataTable();

    const dtHeaderMap = {};
    table.columns().every(function(idx) {
        const headerText = $(this.header()).text().trim().toLowerCase();
        if (headerText) dtHeaderMap[headerText] = idx;
        const colSettings = table.settings()[0].aoColumns[idx];
        if (colSettings && colSettings.sName) dtHeaderMap[colSettings.sName.trim().toLowerCase()] = idx;
    });

    const decoder = document.createElement('textarea');
    const decodeEntities = (str) => {
        if (!str || !str.includes('&')) return str;
        decoder.innerHTML = str; return decoder.value;
    };

    updatedCards.forEach(card => {
        if (!card || !card.id) return;
        const row = table.row((idx, data) => String(data[state.idxId]) === String(card.id));

        if (row.any()) {
            const rowData = row.data();
            let hasChanged = false;
            
            Object.keys(card).forEach(key => {
                if (key === 'id') return; 
                const normalizedKey = key.toLowerCase().replace(/_/g, ' ').trim();
                let idx = dtHeaderMap[normalizedKey] !== undefined ? dtHeaderMap[normalizedKey] : dtHeaderMap[key.toLowerCase().trim()];
                
                if (idx !== undefined && rowData[idx] !== undefined) {
                    const currentVal = rowData[idx] !== null ? decodeEntities(rowData[idx].toString().trim()) : '';
                    const incomingVal = card[key] !== null ? decodeEntities(card[key].toString().trim()) : '';
                    if (currentVal !== incomingVal) hasChanged = true;
                }
            });
            
            row.data(rowData);
            const $card = $(`#card-${card.id}`);
            if ($card.length && hasChanged) {
                if (typeof drawOrHydrateCardComponent === 'function') drawOrHydrateCardComponent(card, $card);
                $card.css('transition', 'all 0.5s ease').css('outline', '2px solid #28a745');
                setTimeout(() => $card.css('outline', 'none'), 2000);
            }
        }
    });
    table.draw(false);
}

const CardLiveFeedUpdater = {
    visibleCardIds: new Set(),
    observer: null,
    updateTimeoutId: null,
    updateIntervalMs: 30000, 
    batchDelayMs: 300,      

    init() {
        this.setupIntersectionObserver();
        this.startPeriodicSync();
        console.log("Card Live Feed Updater Initialized.");
    },

    setupIntersectionObserver() {
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const csrId = entry.target.getAttribute('data-id');
                if (!csrId) return;
                if (entry.isIntersecting) this.visibleCardIds.add(csrId); else this.visibleCardIds.delete(csrId);
            });
            clearTimeout(this.updateTimeoutId);
            this.updateTimeoutId = setTimeout(() => this.triggerBatchUpdate(), this.batchDelayMs);
        }, { root: null, rootMargin: '100px', threshold: 0.1 });

        this.observeGridItems();
        const gridElement = document.getElementById('visual-card-grid');
        if (gridElement) {
            new MutationObserver(() => this.observeGridItems()).observe(gridElement, { childList: true });
        }
    },

    observeGridItems() {
        document.querySelectorAll('#visual-card-grid .card-item').forEach(card => {
            const isVisible = card.checkVisibility ? card.checkVisibility() : (card.offsetWidth > 0 || card.offsetHeight > 0);
            if (isVisible) this.observer.observe(card);
        });
    },

    getCsrfToken() {
        const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenInput) return tokenInput.value;
        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
        return match ? decodeURIComponent(match[1]) : null;
    },

    triggerBatchUpdate() {
        const state = window.CardLiveFeedState;
        if (state.isApplyingServerUpdate || $('.dt-inline-edit:focus').length > 0) return;
        
        const idsToUpdate = Array.from(this.visibleCardIds);
        if (idsToUpdate.length === 0) return;

        $.ajax({
            url: "/get_flat_cards/",
            method: "POST",
            headers: { 'X-CSRFToken': this.getCsrfToken() },
            data: { 'card_ids': idsToUpdate },
            success: (res) => { if (res && res["data"]) patchCardUpdates(res["data"]); },
            error: (xhr) => { console.error("Auto-sync update failed:", xhr.responseText); }
        });
    },

    startPeriodicSync() {
        setInterval(() => { if (document.visibilityState === 'visible') this.triggerBatchUpdate(); }, this.updateIntervalMs);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // CardLiveFeedUpdater.init();
});