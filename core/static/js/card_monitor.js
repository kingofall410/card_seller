const CardMonitor = (function() {
    let instance;

    function createInstance() {
        // This is our moving baseline
        let lastServerTime = new Date().toISOString();
        let callbacks = [];
        let isPolling = false;
        let query = "";

        const poll = async () => {
            // We still check if cards exist just to ensure we're on a results page
            const cardElements = document.querySelectorAll('[data-id]');
            if (cardElements.length === 0) return;

            /*try {
                // We ONLY send the query and the baseline date
                const params = new URLSearchParams({ 
                    q: query, 
                    since: lastServerTime 
                });

                const response = await fetch(`/card_search_ajax/?${params.toString()}`, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                const data = await response.json();

                // IMPORTANT: Update the baseline to the server's clock 
                // to ensure we don't miss or double-count the next window
                if (data.server_time) {
                    lastServerTime = data.server_time;
                }
                
                if ((data.html && data.html.trim() !== "") && (data.total_count > 0)) {
                    console.log(`[CardMonitor] Found updates since ${lastServerTime}`);
                    callbacks.forEach(cb => cb(data));
                }
            } catch (err) {
                console.error("[CardMonitor] Poll Error:", err);
            }*/
        };

        return {
            start: function(currentQuery, interval = 5000) {
                query = currentQuery;
                // Reset baseline whenever a new search starts
                lastServerTime = new Date().toISOString();
                
                if (isPolling) return;
                isPolling = true;
                setInterval(poll, interval);
                poll(); 
            },
            onUpdate: function(callback) {
                callbacks.push(callback);
            }
        };
    }

    return {
        getInstance: function() {
            if (!instance) instance = createInstance();
            return instance;
        }
    };
})();
// Export to window
window.CardMonitor = CardMonitor;