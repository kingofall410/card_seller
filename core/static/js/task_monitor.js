window.StatelessTaskMonitor = (function() {
    let instance;
    const POLL_INTERVAL = 30000;
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
                // 1. Find all day cells on the current page
                const dayCells = document.querySelectorAll('.day-cell[data-date]');
                if (dayCells.length === 0) return;

                // 2. Grab the first and last dates from the grid
                const dates = Array.from(dayCells).map(el => el.dataset.date).sort();
                const startDate = dates[0];
                const endDate = dates[dates.length - 1];
                console.log(endDate)
                // 3. Append them as query parameters
                const url = `/services/task_monitor_data/?start_date=${startDate}&end_date=${endDate}`;
                
                const res = await fetch(url);
                if (!res.ok) return;
                
                const result = await res.json();
                processDiff(previousData, result.data);
                
                previousData = JSON.parse(JSON.stringify(result.data)); 
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify(previousData));

            } catch (err) {
                console.error("[StatelessTaskMonitor] Fetch error:", err);
            }
        };

        const processDiff = (oldData, newData) => {
            if (!oldData || oldData.length === 0) {
                // First run: just establish the baseline
                return; 
            }

            const oldMap = Object.fromEntries(oldData.map(t => [t.id, t.status]));
            console.log(oldData, newData)
            newData.forEach(task => {
                const prevStatus = oldMap[task.id];
                
                // Use the ID directly since our Django view now provides it
                const taskId = task.id;

                if (prevStatus !== undefined) {
                    // Case 1: Status Change
                    if (prevStatus !== task.status) {
                        callbacks.forEach(cb => cb(taskId, task, false));
                    }
                } else {
                    // Case 2: Brand New Task (or moved into range)
                    callbacks.forEach(cb => cb(taskId, task, true));
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