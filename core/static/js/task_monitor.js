window.StatelessTaskMonitor = (function() {
    let instance;
    const POLL_INTERVAL = 5000;
    const callbacks = [];
    
    // Create a unique key based on the current URL path
    const STORAGE_KEY = `task_monitor_cache_${window.location.pathname}`;

    let previousData = []; 

    function init() {
        console.log(`[StatelessTaskMonitor] Initialized for page: ${window.location.pathname}`);

        const checkUpdates = async () => {
            await performFetch();
        };

        const performFetch = async () => {
            try {
                const res = await fetch('/services/task_monitor_data/');
                if (!res.ok) return;
                
                const result = await res.json();
                const newData = result.data;

                // 1. Process the difference
                processDiff(previousData, newData);

                // 2. Update memory and sessionStorage
                previousData = JSON.parse(JSON.stringify(newData)); 
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify(previousData));

            } catch (err) {
                console.error("[StatelessTaskMonitor] Fetch error:", err);
            }
        };

        const processDiff = (oldData, newData) => {
            // If no baseline, skip to avoid mass-reloading everything on first load
            if (!oldData || oldData.length === 0) return;

            const oldMap = Object.fromEntries(oldData.map(t => [t.name, t.status]));
            
            newData.forEach(task => {
                const prevStatus = oldMap[task.name];
                
                if (prevStatus !== undefined && prevStatus !== task.status) {
                    const idMatch = task.name.match(/(\d+)$/);
                    if (idMatch) {
                        const cardId = idMatch[0];
                        console.log(`[Delta] Change on ${window.location.pathname} for Card ${cardId}: ${prevStatus} -> ${task.status}`);
                        callbacks.forEach(cb => cb(cardId, task.status));
                    }
                }
            });
        };

        // LOAD INITIAL STATE: Per-page scope via sessionStorage
        const saved = sessionStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                previousData = JSON.parse(saved);
            } catch (e) {
                console.error("Failed to parse session cache", e);
            }
        }

        setInterval(checkUpdates, POLL_INTERVAL);
        checkUpdates();

        return {
            onUpdate: (cb) => callbacks.push(cb)
        };
    }

    return {
        getInstance: function() {
            if (!instance) instance = init();
            return instance;
        }
    };
})();