const AppOrchestrator = {
    state: {
        currentPage: 1,
        hasNextPage: false,
        isLoading: false,
        currentQuery: ""
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

        // 3. LOAD FROM CACHE ON PAGE LOAD
        this.loadFromCache();
    },

    loadFromCache() {
        const cachedHTML = sessionStorage.getItem('last_search_html');
        const cachedQuery = sessionStorage.getItem('last_search_query');
        const cachedPage = sessionStorage.getItem('last_search_page');
        const cachedNext = sessionStorage.getItem('last_search_hasNext');

        if (cachedHTML && cachedQuery) {
            const cardList = document.getElementById('global-card-list');
            if (cardList) {
                cardList.innerHTML = cachedHTML;
                
                // Update displayed count based on cached items, if they're filtered it'll get overwritten
                const countDisplayed = document.getElementById('count-displayed');
                if (countDisplayed) {
                    
                    countDisplayed.innerText = cardList.querySelectorAll('.card-item:not(.folder)').length;
                }
            }
            
            // Restore total count from session storage
            const countTotal = document.getElementById('count-total');
            const cachedTotal = sessionStorage.getItem('last_search_total');
            if (countTotal && cachedTotal) {
                countTotal.innerText = cachedTotal;
            }
            
            this.refreshUI();
        }
    },

    refreshUI() {
        if (typeof buildDropdowns === 'function') buildDropdowns();
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
            sessionStorage.removeItem('last_search_html'); // Clear old cache
        }

        this.state.isLoading = true;
        const spinner = document.getElementById('search-spinner');
        if (spinner) spinner.style.display = "block";

        try {
            const response = await fetch(
                `/card_search_ajax/?q=${encodeURIComponent(this.state.currentQuery)}&page=${this.state.currentPage}`,
                { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
            );
            const data = await response.json();

            // 1. Insert HTML as usual
            if (isNewSearch) {
                cardList.innerHTML = data.html || ''; 
            } else {
                cardList.insertAdjacentHTML('beforeend', data.html || '');
            }

            // 2. Update the Counters
            const countDisplayed = document.getElementById('count-displayed');
            const countTotal = document.getElementById('count-total');

            if (countTotal) {
                // data.total_count should be sent from your Django View
                countTotal.innerText = data.total_count || 0;
            }

            if (countDisplayed) {
                // Count the actual card elements currently in the list
                const currentCards = cardList.querySelectorAll('.card-item:not(.hidden-card):not(.folder)').length;
                countDisplayed.innerText = currentCards;
            }

            // Update State
            this.state.hasNextPage = data.has_next;
            this.state.currentPage = data.next_page;

            // --- CACHE THE UPDATE ---
            sessionStorage.setItem('last_search_html', cardList.innerHTML);
            sessionStorage.setItem('last_search_page', this.state.currentPage);
            sessionStorage.setItem('last_search_hasNext', this.state.hasNextPage);
            sessionStorage.setItem('last_search_total', data.total_count);

            this.refreshUI();

            this.state.isLoading = false; 

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