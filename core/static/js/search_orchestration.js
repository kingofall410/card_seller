const AppOrchestrator = {
    state: {
        currentPage: 1,
        hasNextPage: false,
        isLoading: false,
        currentQuery: "",
        timeframe: "30" // Default days
    },

    init() {
        // 1. Listen for New Search Trigger
        document.addEventListener('cardSearchTriggered', (e) => {
            this.state.currentQuery = e.detail.query;
            sessionStorage.setItem('last_search_query', e.detail.query);
            this.performSearch(true); 
        });

        // 2. Infinite Scroll Logic
        window.addEventListener('scroll', () => {
            if (this.state.isLoading || !this.state.hasNextPage || !this.state.currentQuery) return;
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 600) {
                this.performSearch(false);
            }
        });

        this.loadFromCache();
        this.setupCardMonitor();
    },

    getSinceDate(days) {
        const d = new Date();
        d.setDate(d.getDate() - parseInt(days));
        return d.toISOString().split('T')[0]; 
    },

    updateTimeframe(days) {
        this.state.timeframe = days;
        sessionStorage.setItem('last_search_timeframe', days);
        this.performSearch(true);
    },

    setupCardMonitor() {
        const cardMon = CardMonitor.getInstance();
        cardMon.onUpdate((data) => {
            const temp = document.createElement('div');
            temp.innerHTML = data.html;
            temp.querySelectorAll('[data-card-id]').forEach(newCard => {
                const cardId = newCard.getAttribute('data-card-id');
                const existingCard = document.querySelector(`[data-card-id="${cardId}"]`);
                if (existingCard) {
                    existingCard.outerHTML = newCard.outerHTML;
                    const el = document.querySelector(`[data-card-id="${cardId}"]`);
                    el.classList.add('is-updating');
                    setTimeout(() => el.classList.remove('is-updating'), 1000);
                }
            });

            if (data.table_data && data.table_data.length > 0 && typeof updateSpreadsheet === 'function') {
                //updateSpreadsheet(data.table_data, data.col_headers, true);
            }
        });
    },

    loadFromCache() {
        const cachedHTML = sessionStorage.getItem('last_search_html');
        const cachedQuery = sessionStorage.getItem('last_search_query');
        const cachedTableData = sessionStorage.getItem('last_search_table_data');
        const cachedHeaders = sessionStorage.getItem('last_search_col_headers');
        const cachedTimeframe = sessionStorage.getItem('last_search_timeframe');

        if (cachedTimeframe) {
            this.state.timeframe = cachedTimeframe;
            const radio = document.querySelector(`input[name="search-timeframe"][value="${cachedTimeframe}"]`);
            if (radio) radio.checked = true;
        }

        if (cachedHTML && cachedQuery) {
            this.state.currentQuery = cachedQuery;
            const cardList = document.getElementById('global-card-list');
            if (cardList) cardList.innerHTML = cachedHTML;
            
            if (cachedTableData && cachedHeaders && typeof updateSpreadsheet === 'function') {
                //updateSpreadsheet(JSON.parse(cachedTableData), JSON.parse(cachedHeaders));
            }

            this.refreshUI();
            CardMonitor.getInstance().start(this.state.currentQuery);
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
        
        const cardList = document.getElementById('global-card-list');
        
        if (isNewSearch) {
            this.state.currentPage = 1;
            if (cardList) cardList.innerHTML = ''; 
            sessionStorage.removeItem('last_search_html');
            sessionStorage.removeItem('last_search_table_data');
            sessionStorage.removeItem('last_search_col_headers');
        }

        this.state.isLoading = true;
        const spinner = document.getElementById('search-spinner');
        if (spinner) spinner.style.display = "block";

        try {
            const sinceDate = this.getSinceDate(this.state.timeframe);
            
            // BUILD THE URL
            // If it's NOT a new search (meaning it's the auto-loader loop), 
            // we could optionally add updates_only=1 if you wanted to bypass 
            // the paginator on the backend for those specific calls.
            let url = `/card_search_ajax/?q=${encodeURIComponent(this.state.currentQuery)}&page=${this.state.currentPage}&since=${sinceDate}`;
            
            // We only add updates_only if we are NOT on the first page of a fresh search
            // but your backend logic uses this to skip pagination entirely.
            // Note: If you want infinite scroll to stay paginated, keep this off.
            // If you want the "rest of the results" to dump in one go, uncomment below:
            // if (!isNewSearch) url += '&updates_only=1';

            const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await response.json();

            if (isNewSearch) {
                cardList.innerHTML = data.html || ''; 
            } else {
                cardList.insertAdjacentHTML('beforeend', data.html || '');
            }

            if (isNewSearch && data.table_data && data.table_data.length > 0) {
                if (typeof updateSpreadsheet === 'function') {
                    //updateSpreadsheet(data.table_data, data.col_headers);
                    sessionStorage.setItem('last_search_table_data', JSON.stringify(data.table_data));
                    sessionStorage.setItem('last_search_col_headers', JSON.stringify(data.col_headers));
                }
            }

            const countTotal = document.getElementById('count-total');
            if (countTotal) countTotal.innerText = data.total_count || 0;

            this.state.hasNextPage = data.has_next;
            this.state.currentPage = data.next_page;

            sessionStorage.setItem('last_search_html', cardList.innerHTML);
            sessionStorage.setItem('last_search_page', this.state.currentPage);
            sessionStorage.setItem('last_search_hasNext', this.state.hasNextPage);
            sessionStorage.setItem('last_search_total', data.total_count);
            sessionStorage.setItem('last_search_timeframe', this.state.timeframe);

            this.refreshUI();
            this.state.isLoading = false; 

            if (isNewSearch) {
                CardMonitor.getInstance().start(this.state.currentQuery);
            }

            // AUTO-PAGINATION LOOP
            if (this.state.hasNextPage) {
                setTimeout(() => this.performSearch(false), 50);
            } else {
                if (spinner) spinner.style.display = "none";
            }

        } catch (err) {
            console.error("Search failed:", err);
            this.state.isLoading = false;
            if (spinner) spinner.style.display = "none";
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // 1. Setup listeners and check for existing cache
    AppOrchestrator.init();

    // 2. Setup the UI structure
    buildDropdowns(); 
    buildSortBar();

    // 3. ONLY search if there is no cache
    const hasCache = sessionStorage.getItem('last_search_html');
    
    if (!hasCache) {
        // No cache found, run the initial default search
        AppOrchestrator.performSearch(true); 
    } else {
        // Cache was already loaded by .init() -> .loadFromCache()
        // We just hide the spinner in case it was defaulting to 'block'
        const spinner = document.getElementById('search-spinner');
        if (spinner) spinner.style.display = "none";
        
        console.log("Instant load from cache successful.");
    }
});