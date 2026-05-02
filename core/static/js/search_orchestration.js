const AppOrchestrator = {
    state: {
        currentPage: 1,
        hasNextPage: false,
        isLoading: false,
        currentQuery: "",
        timeframe: "30", // Default days
        activeFilters: {}
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

    updateFilters(newFilters) {
        if (newFilters) {
            this.state.activeFilters = newFilters;
        }
        //this.performSearch(true); // Reset to page 1 for filtered results
    },

    getSinceDate(days) {
        const d = new Date();
        d.setDate(d.getDate() - parseInt(days));
        return d.toISOString().split('T')[0]; 
    },

    updateTimeframe(days) {
        this.state.timeframe = days;
        sessionStorage.setItem('last_search_timeframe', days);
        //this.performSearch(true);
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
            //CardMonitor.getInstance().start(/*this.state.currentQuery*/);
        }
    },

    refreshUI() {
        if (typeof window.buildDropdowns === 'function') window.buildDropdowns();
        if (typeof buildSortBar === 'function') buildSortBar(); 
        if (typeof applyFilters === 'function') applyFilters();
        if (typeof sortCards === 'function') sortCards(); 
    },
    flattenFilters(activeFilters) {
        console.log("active filters pre flat:", activeFilters)
        const flatList = [];
        Object.keys(activeFilters).forEach(field => {
            const filters = activeFilters[field];
            if (Array.isArray(filters)) {
                filters.forEach(f => {
                    flatList.push({
                        field: field, // Inject the field name here!
                        op: f.op,
                        val: f.val
                    });
                });
            }
        });
        console.log("active filters post flat:", flatList)
        return flatList;
    },
    async performSearch(isNewSearch = true) {
        if (this.state.isLoading) return;
        console.log("performSearch", isNewSearch)
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
            let sinceString = "";
            if (this.state.timeframe > 0) {
                sinceString = `&since=${this.getSinceDate(this.state.timeframe)}`;
            }
            console.log("Active filters: ", this.state.activeFilters)
            // BUILD URL with Filters
            let url = `/card_search_ajax/?q=${encodeURIComponent(this.state.currentQuery)}&page=${this.state.currentPage}${sinceString}`;
            console.log(this.state.activeFilters)
            // Add filters if they exist
            if (Object.keys(this.state.activeFilters).length > 0) {
                const flatFilters = this.state.activeFilters//this.flattenFilters(this.state.activeFilters);
                console.log("Flat", flatFilters);
                url += `&filters=${encodeURIComponent(JSON.stringify(flatFilters))}`;
            }

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
            const RENDER_LIMIT = 200;

            // Update the count based on how many items were added in the last batch
            const newItemsCount = document.querySelectorAll('.card-item').length; 
            this.state.renderedCount = newItemsCount;

            if (this.state.hasNextPage && this.state.renderedCount < RENDER_LIMIT) {
                // Continue loop
                setTimeout(() => this.performSearch(false), 50);
            } else {
                // Stop loop: either no more pages or limit reached
                if (spinner) spinner.style.display = "none";
                
                if (this.state.renderedCount >= RENDER_LIMIT) {
                    console.log("Render limit of 200 reached. Switching to manual scroll.");
                }
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
        //AppOrchestrator.performSearch(true); 
    } else {
        // Cache was already loaded by .init() -> .loadFromCache()
        // We just hide the spinner in case it was defaulting to 'block'
        const spinner = document.getElementById('search-spinner');
        if (spinner) spinner.style.display = "none";
        
        console.log("Instant load from cache successful.");
    }
});