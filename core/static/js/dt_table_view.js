async function processQuickEditQueue() {
    const state = window.CardLiveFeedState;
    if (state.isProcessingQueue || state.quickEditQueue.length === 0) return;
    state.isProcessingQueue = true;

    const tableApi = $('#card-data-engine').DataTable();
    const nextPayload = state.quickEditQueue.shift();
    const originalPristineValues = {}; 
    const allTargetCsrIds = [nextPayload.csrId, ...nextPayload.mirroredCsrIds].map(String);

    console.log(`[Optimistic UI] Mutating fields locally for asset: ${nextPayload.csrId}`);

    tableApi.rows().every(function(idx) {
        const d = this.data();
        const rowCsrId = String(d[state.idxCsrId]);

        if (allTargetCsrIds.includes(rowCsrId)) {
            const colIdx = state.headerMap[nextPayload.column.replace('_', ' ').toLowerCase()];
            if (colIdx !== undefined) {
                if (!originalPristineValues[rowCsrId]) {
                    const currentInput = $(this.node()).find(`td:eq(${colIdx}) .dt-inline-edit`);
                    originalPristineValues[rowCsrId] = currentInput.attr('data-current') || '';
                }
                d[colIdx] = nextPayload.value; 
                this.data(d); 

                const cell = tableApi.cell(idx, colIdx);
                const $cellNode = $(cell.node());
                $cellNode.addClass('dt-cell-committed');
                setTimeout(() => $cellNode.removeClass('dt-cell-committed'), 800);
            }
        }
    });

    tableApi.draw(false);
    restoreInputFocusLock(tableApi);

    try {
        console.log(`[Debug] Syncing CSR: ${nextPayload.csrId} for field: ${nextPayload.column}`);
        const token = (typeof CardLiveFeedUpdater !== 'undefined' ? CardLiveFeedUpdater.getCsrfToken() : '');
        
        await $.ajax({
            url: "/bulk_update_csr_fields/",
            method: "POST",
            contentType: "application/json",
            headers: { 'X-CSRFToken': token },
            data: JSON.stringify({ 
                updates: [{ csrId: nextPayload.csrId, allFields: { [nextPayload.column]: nextPayload.value, [nextPayload.column+"_is_manual"]: true} }] 
            })
        });

        const colIdx = state.headerMap[nextPayload.column.replace('_', ' ').toLowerCase()];
        if (colIdx !== undefined) {
            allTargetCsrIds.forEach(targetCsrId => {
                $(`#card-data-engine tbody tr`).each(function() {
                    const $cellInput = $(this).find(`td:eq(${colIdx}) .dt-inline-edit`);
                    if ($cellInput.length) {
                        $cellInput.attr('data-current', nextPayload.value);
                    }
                });
            });
        }
    } catch (xhr) {
        console.error("[CRITICAL BACKGROUND ERROR] Server sync rejected:", xhr.responseText);
        tableApi.rows().every(function() {
            const d = this.data();
            const rowCsrId = String(d[state.idxCsrId]);
            if (allTargetCsrIds.includes(rowCsrId) && originalPristineValues[rowCsrId] !== undefined) {
                const colIdx = state.headerMap[nextPayload.column.replace('_', ' ').toLowerCase()];
                const revertVal = originalPristineValues[rowCsrId];
                d[colIdx] = revertVal;
                this.data(d);
                $(this.node()).find(`td:eq(${colIdx}) .dt-inline-edit`).val(revertVal);
            }
        });
        tableApi.draw(false);
        restoreInputFocusLock(tableApi);
        alert("Background update sync failed. Row values have been safely rolled back.");
    } finally {
        state.isProcessingQueue = false;
        processQuickEditQueue();
    }
}

function restoreInputFocusLock(tableApi) {
    const state = window.CardLiveFeedState;
    if (!state.activeFocusLock) return;
    tableApi.rows().every(function() {
        if (this.data()[state.idxId] == state.activeFocusLock.id) {
            const colIdx = state.headerMap[state.activeFocusLock.column];
            const $input = $(this.node()).find(`td:eq(${colIdx}) .dt-inline-edit`);
            if ($input.length) {
                $input.focus();
                if (state.activeFocusLock.selectionStart !== undefined) {
                    $input[0].setSelectionRange(state.activeFocusLock.selectionStart, state.activeFocusLock.selectionStart);
                }
            }
            return false;
        }
    });
}

// Initialize Native Table Logic
(function($) {
    $(function() {
        const state = window.CardLiveFeedState;

        const table = $('#card-data-engine').DataTable({
            dom: 'ift',
            pageLength: 50,
            searchPanes: { 
                container: '#panes-container', layout: 'columns-1', stateSave: true,
                cascadePanes: false, initCollapsed: true, columns: [6,10,1,2,9,12,17]
            },
            columnDefs: [
                { 
                    targets: 0, 
                    orderable: false, 
                    render: (d, t, r) => `<input type="checkbox" class="dt-row-chk" data-id="${r[state.idxId]}">` 
                },
                { 
                    searchPanes: { show: true, initCollapsed: false, sortable: true, dtOpts: { order: [[1, 'desc']] } }, 
                    targets: [6] 
                },
                { 
                    searchPanes: { show: true, dtOpts: { order: [[1, 'desc']] } }, 
                    targets: [1,2,3,4,5,7,8] 
                },
                { 
                    searchPanes: { show: true, initCollapsed: false, dtOpts: { order: [[1, 'desc']] } }, 
                    targets: [10], 
                    visible: false 
                }, 
                { 
                    searchPanes: { show: true, dtOpts: { order: [[0, 'desc']] } }, 
                    targets: [11,12,17], 
                    type: 'num', 
                    visible: false 
                },  
                { 
                    targets: [20], 
                    type: 'date', 
                    visible: false 
                },   
                { 
                    targets: [state.idxFrontUrl, state.idxReverseUrl], 
                    type: 'display' 
                },  
                { 
                    targets: [15,16,19,21,23,24], 
                    visible: false 
                },
                { 
                    targets: '_all',
                    render: function(data, type, row, meta) {
                        if (type === 'display') {
                            const colIdx = meta.col;
                            
                            // Explicitly guard structural metadata fields from being overwritten by inputs
                            const isProtected = (
                                colIdx === 0 || 
                                colIdx === state.idxId || 
                                colIdx === state.idxCsrId || 
                                colIdx === state.idxFrontUrl || 
                                colIdx === state.idxReverseUrl || 
                                colIdx === state.idxFrontHdUrl || 
                                colIdx === state.idxReverseHdUrl
                            );
                            
                            const isImg = (colIdx === state.idxFrontUrl || colIdx === state.idxReverseUrl);
                            
                            if (isImg) {
                                return createImageRenderer(data);
                            } else if (!isProtected) {
                                return createPersistentInputRenderer(data);
                            }
                        }
                        return data;
                    }
                }
            ],
            infoCallback: (s, start, end, max, total) => `Showing ${total} card${total !== 1 ? 's' : ''} of ${max}`,
            initComplete: function() {
                const api = this.api();
                state.idxId = api.columns().header().toArray().findIndex(th => $(th).text().trim() === 'ID');
                
                api.searchPanes.container().appendTo('#panes-container');
                $('.dataTables_info').appendTo('#header-info-mount');
                if (typeof buildSortBar === 'function') buildSortBar(api, state.headerMap);
                
                // Dispatch event signaling table rendering engine complete
                $(document).trigger('dt:engine-ready', [api]);
            }
        });

        // Inline Interaction Handling Mechanics
        $('#card-data-engine tbody').on('input', '.dt-inline-edit', function() {
            const $input = $(this);
            const updatedVal = $input.val().trim();
            if (updatedVal === $input.attr('data-current')) return;

            const cellIdx = table.cell($input.closest('td')).index();
            const columnName = table.column(cellIdx.column).header().textContent.trim().toLowerCase().replace(' ', '_');
            const rData = table.row(cellIdx.row).data();

            if (state.activeFocusLock && state.activeFocusLock.id == rData[state.idxId]) {
                state.activeFocusLock.selectionStart = this.selectionStart;
            }

            const changePayload = { csrId: rData[state.idxCsrId].toString().trim(), column: columnName, value: updatedVal, mirroredCsrIds: [] };

            table.rows().indexes().each((idx) => {
                const loopData = table.row(idx).data();
                if (Array.from(state.selectedIds).includes(loopData[state.idxId]) && loopData[state.idxCsrId] !== changePayload.csrId) {
                    changePayload.mirroredCsrIds.push(loopData[state.idxCsrId]);
                    $(table.cell(idx, cellIdx.column).node()).find('.dt-inline-edit').val(updatedVal);
                }
            });

            clearTimeout(state.quickEditDebounceTimer);
            state.quickEditDebounceTimer = setTimeout(() => {
                state.quickEditQueue.push(changePayload);
                processQuickEditQueue();
            }, 750); 
        });

        $('#card-data-engine tbody').on('keydown', '.dt-inline-edit', function(evt) {
            if (evt.which === 13) { 
                evt.preventDefault(); $(this).blur(); 
                const $nextRow = $(this).closest('tr').next('tr'); 
                if ($nextRow.length) {
                    const $nextInput = $nextRow.find(`td:eq(${$(this).closest('td').index()}) .dt-inline-edit`);
                    if ($nextInput.length) { $nextInput.focus().trigger('mouseenter'); }
                }
            } else if (evt.which === 27) { 
                evt.preventDefault(); $(this).val($(this).attr('data-current')).blur(); 
            }
        });

        $('#card-data-engine tbody').on('focus', '.dt-inline-edit', function() {
            setTimeout(() => { $(this).select(); }, 25); 
        });
    });
})(jQuery);