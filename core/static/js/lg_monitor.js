// Check if it's already defined to prevent redeclaration errors
if (typeof window.LGMonitor === 'undefined') {

    const LGMonitor = (function() {
        let instance;

        function createInstance() {
            let lastServerTime = new Date().toISOString();
            let watchedGroupIds = new Set();
            let isPolling = false;

            const poll = async () => {
                if (watchedGroupIds.size === 0) return;

                try {
                    const params = new URLSearchParams({ since: lastServerTime });
                    watchedGroupIds.forEach(id => params.append('ids[]', id));

                    const response = await fetch(`/async_lg_monitor/?${params.toString()}`, {
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    
                    if (!response.ok) return;
                    const data = await response.json();
                    console.log(data)
                    if (data.server_time) lastServerTime = data.server_time;

                    if (data.html && data.html.trim() !== "") {
                        console.log("here")
                        const temp = document.createElement('div');
                        temp.innerHTML = data.html;
                        const updatedNodes = temp.querySelectorAll('[data-listing-group]');
                        console.log("updatedNodes")
                        updatedNodes.forEach(newNode => {
                            const gid = newNode.dataset.groupId;
                            const existingNode = document.getElementById(`lg-${gid}`);
                            if (existingNode) {
                                console.log(`[LGMonitor] Patching refreshed group: ${gid}`);
                                existingNode.outerHTML = newNode.outerHTML;
                                // Stop watching once successfully updated
                                watchedGroupIds.delete(gid);
                            }
                        });
                    }
                } catch (err) {
                    console.error("[LGMonitor] Error:", err);
                }
            };

            return {
                watchGroup: function(groupId) {
                    watchedGroupIds.add(groupId.toString());
                    console.log(`[LGMonitor] Watching Group ${groupId}`);
                    
                    if (!isPolling) {
                        isPolling = true;
                        setInterval(poll, 10000); 
                        poll(); 
                    }
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

    // Attach to window only once
    window.LGMonitor = LGMonitor;
}