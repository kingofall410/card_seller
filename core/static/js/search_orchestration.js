const AppOrchestrator = {
    state: {
        currentPage: 1,
        hasNextPage: false,
        isLoading: false,
        currentQuery: "",
        timeframe: "30",
        activeFilters: {},
        renderedCount: 0
    },

    init() {
        // 1. New Search Trigger
        document.addEventListener('cardSearchTriggered', (e) => {
            this.state.currentQuery = e.detail.query;
            sessionStorage.setItem('last_search_query', e.detail.query);
            this.performSearch(true);
        });

        // 2. Scroll Logic - Attached to Window AND Container for safety
        const scrollHandler = () => {
            if (this.state.isLoading || !this.state.hasNextPage || !this.state.currentQuery) return;

            // Use the more robust height calculation
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            const windowHeight = window.innerHeight;
            const docHeight = Math.max(
                document.body.scrollHeight, document.documentElement.scrollHeight,
                document.body.offsetHeight, document.documentElement.offsetHeight
            );

            // Trigger when within 1000px of bottom
            if (scrollTop + windowHeight >= docHeight - 1000) {
                console.log("Scroll trigger active: Fetching next page");
                this.performSearch(false);
            }
        };

        window.addEventListener('scroll', scrollHandler);
        
        this.loadFromCache();
        this.setupCardMonitor();
    },

    // ... (updateFilters, getSinceDate, updateTimeframe remains same as previous) ...
    updateFilters(newFilters) { this.state.activeFilters = newFilters; },
    getSinceDate(days) {
        const d = new Date();
        d.setDate(d.getDate() - parseInt(days));
        return d.toISOString().split('T')[0];
    },
    updateTimeframe(days) {
        this.state.timeframe = days;
        sessionStorage.setItem('last_search_timeframe', days);
    },

    setupCardMonitor() {
        const cardMon = CardMonitor.getInstance();
        cardMon.onUpdate((data) => {
            const temp = document.createElement('div');
            temp.innerHTML = data.html;
            temp.querySelectorAll('[data-id]').forEach(newCard => {
                const cardId = newCard.getAttribute('data-id');
                const existingCard = document.querySelector(`.card-item[data-id="${cardId}"]`);
                if (existingCard) {
                    existingCard.outerHTML = newCard.outerHTML;
                    const el = document.querySelector(`.card-item[data-id="${cardId}"]`);
                    el.classList.add('is-updating');
                    setTimeout(() => el.classList.remove('is-updating'), 1000);
                }
            });
        });
    },

    loadFromCache() {
        const cachedHTML = sessionStorage.getItem('last_search_html');
        const cachedQuery = sessionStorage.getItem('last_search_query');
        if (cachedHTML && cachedQuery) {
            this.state.currentQuery = cachedQuery;
            const cardList = document.getElementById('global-card-list');
            if (cardList) cardList.innerHTML = cachedHTML;
            this.refreshUI();
        }
    },

    refreshUI() {
        if (typeof window.buildDropdowns === 'function') window.buildDropdowns();
        if (typeof buildSortBar === 'function') buildSortBar();
        if (typeof applyFilters === 'function') applyFilters();
        if (typeof sortCards === 'function') sortCards();
    },

    async performSearch(isNewSearch = true) {
        if (this.state.isLoading) return;

        const spinner = document.getElementById('search-spinner');
        const cardList = document.getElementById('global-card-list');

        // Show spinner and FORCE browser paint break
        if (spinner) spinner.style.display = "block";
        await new Promise(r => setTimeout(r, 20)); 

        if (isNewSearch) {
            this.state.currentPage = 1;
            if (cardList) cardList.innerHTML = '';
        }

        this.state.isLoading = true;

        try {
            let sinceString = this.state.timeframe > 0 ? `&since=${this.getSinceDate(this.state.timeframe)}` : "";
            let url = `/card_search_ajax/?q=${encodeURIComponent(this.state.currentQuery)}&page=${this.state.currentPage}${sinceString}`;

            if (Object.keys(this.state.activeFilters).length > 0) {
                url += `&filters=${encodeURIComponent(JSON.stringify(this.state.activeFilters))}`;
            }

            const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await response.json();

            if (isNewSearch) {
                cardList.innerHTML = data.html || '';
            } else {
                cardList.insertAdjacentHTML('beforeend', data.html || '');
            }

            // UI and State Updates
            this.state.hasNextPage = data.has_next;
            this.state.currentPage = data.next_page;
            this.state.renderedCount = document.querySelectorAll('.card-item').length;
            
            const countTotal = document.getElementById('count-total');
            if (countTotal) countTotal.innerText = data.total_count || 0;

            sessionStorage.setItem('last_search_html', cardList.innerHTML);
            this.refreshUI();

            // ORCHESTRATION LOGIC
            const RENDER_LIMIT = 400; // Changed to 40 as per your last request
            
            this.state.isLoading = false; // UNLOCK before loop/scroll check

            if (this.state.hasNextPage && this.state.renderedCount < RENDER_LIMIT) {
                // Keep looping automatically
                setTimeout(() => this.performSearch(false), 50);
            } else {
                // Done auto-loading. If there are still more pages, scroll listener is now active
                if (spinner) spinner.style.display = "none";
                console.log(`Auto-pagination stopped at ${this.state.renderedCount}. Scroll to load more.`);
            }

        } catch (err) {
            console.error("Search failed:", err);
            this.state.isLoading = false;
            if (spinner) spinner.style.display = "none";
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    AppOrchestrator.init();
    buildDropdowns();
    buildSortBar();

    const hasCache = sessionStorage.getItem('last_search_html');
    if (hasCache) {
        const spinner = document.getElementById('search-spinner');
        if (spinner) spinner.style.display = "none";
    }
});