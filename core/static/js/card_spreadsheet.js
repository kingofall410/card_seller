const SpreadsheetModule = (function() {
    let hotInstance = null;
    let isApplyingServerUpdate = false;

    // --- Private Renderers ---
    function imageRenderer(instance, td, row, col, prop, value, cellProperties) {
        td.innerHTML = '';
        if (value) {
            const img = document.createElement('img');
            img.src = value;
            img.style.width = '200px';
            img.style.height = '300px';
            img.style.display = 'block';
            img.style.margin = '0 auto';
            td.appendChild(img);
        } else {
            td.innerText = 'No Image';
        }
        return td;
    }

    // --- Core Logic ---
    return {
        init: function(containerId, tableData, colHeaders) {
            console.log("spreadsheet init", containerId, tableData, colHeaders)
            const container = document.getElementById(containerId);
            if (!container) return;

            const columnSettings = colHeaders.map(header => {
                const isImage = header.toLowerCase() === 'front_url' || header.toLowerCase() === 'reverse_url';
                const isId = header.toLowerCase() === 'id';
                return {
                    data: header.toLowerCase().replace(/\s+/g, '_'),
                    readOnly: isId || isImage,
                    renderer: isImage ? imageRenderer : undefined,
                    className: 'htMiddle'
                };
            });

            if (!hotInstance) {
                hotInstance = new Handsontable(container, {
                    data: tableData,
                    colHeaders: colHeaders,
                    columns: columnSettings,
                    rowHeaders: false,
                    stretchH: 'all',
                    autoRowSize: { syncLimit: '100%' },
                    dropdownMenu: true,
                    licenseKey: 'non-commercial-and-evaluation',
                    viewportRowRenderingOffset: 20, // Helps with smooth scrolling
                    manualRowResize: true, // Allows you to manually adjust if it still looks off
                    
                    afterChange: function (changes, source) {
                        if (source === 'loadData' || isApplyingServerUpdate) return;

                        const rowChanges = {};

                        changes.forEach(([row, prop, oldVal, newVal]) => {
                            if (oldVal === newVal) return;

                            if (!rowChanges[row]) rowChanges[row] = {};

                            // Normalization: If newVal is null, undefined, or empty, send ""
                            // This handles when a user hits 'Delete' or 'Backspace' in a cell
                            const sanitizedValue = (newVal === null || newVal === undefined) ? "" : newVal;

                            const fieldName = prop; 
                            rowChanges[row][fieldName] = sanitizedValue;
                            
                            // Set the manual flag
                            rowChanges[row][`${fieldName}_is_manual`] = true;
                        });

                        // Process rows
                        Object.entries(rowChanges).forEach(([rowIndex, fields]) => {
                            const row = parseInt(rowIndex);
                            const rowData = hotInstance.getSourceDataAtRow(row);

                            // Final payload assembly
                            const payload = {
                                // Ensure defaults are also strings, not nulls
                                brand: rowData.brand || "",
                                city: rowData.city || "",
                                ...fields
                            };

                            quickEdit(hotInstance, row, payload);
                        });
                    }
                });
            } else {
                hotInstance.loadData(tableData);
            }
        },

        syncToServer: function(visualRow, updatedFields) {
            const csrId = hotInstance.getDataAtRowProp(visualRow, 'id');
            if (!csrId) return;

            $.ajax({
                url: "/update_csr_fields/",
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify({ csrId: csrId, allFields: updatedFields }),
                success: response => {
                    const serverData = response.search_result;
                    //this.applyUpdate(visualRow, serverData);
                    // Trigger external UI sync if available
                    if (window.syncCardView) window.syncCardView(csrId, serverData);
                }
            });
        },

        applyUpdate: function(visualRow, serverData) {
            console.log(visualRow, serverData)
            hotInstance.batch(() => {
                isApplyingServerUpdate = true;
                Object.entries(serverData).forEach(([field, value]) => {
                    if (hotInstance.propToCol(field) !== -1) {
                        hotInstance.setDataAtRowProp(visualRow, field, value, 'serverUpdate');
                    }
                });
                isApplyingServerUpdate = false;
            });
        },

        filterByCardIds: function(visibleIds) {
            if (!hotInstance) return;
            const filtersPlugin = hotInstance.getPlugin('filters');
            const colHeaders = hotInstance.getColHeader();
            const idColIndex = colHeaders.findIndex(h => h.toLowerCase() === 'card_id');

            if (idColIndex === -1) return;

            console.log("Spreadsheet.filterByCardIds", visibleIds, idColIndex);
            filtersPlugin.clearConditions(idColIndex);
            if (visibleIds.length > 0) {
                filtersPlugin.addCondition(idColIndex, 'by_value', [visibleIds.map(Number)]);
            } else {
                filtersPlugin.addCondition(idColIndex, 'by_value', [['__NONE__']]);
            }
            filtersPlugin.filter();
            hotInstance.render();
        },

        getInstance: () => hotInstance
    };

    function quickEdit(hot, visualRow, updatedFields) {
        console.log("QE", hot, visualRow);

        // Step 1: Get visible row data
        const visibleRowData = hot.getDataAtRow(visualRow);
        const csrId = visibleRowData[2];

        // Step 2: Resolve source index using getSourceDataArray
        const sourceData = hot.getSourceDataArray();
        const sourceRowIndex = sourceData.findIndex(row => String(row[2]) == csrId);

        if (sourceRowIndex < 0) {
            console.warn("Source row not found for csrId:", csrId);
            return;
        }

        // Step 3: Send update to server
        $.ajax({
            url: "/update_csr_fields/",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({
            csrId: csrId,
            allFields: updatedFields
            }),
            success: response => {
            const updatedFields = response.search_result;
            const visualRowIndex = hot.toVisualRow(sourceRowIndex);
            console.log(visualRowIndex)
            if (visualRowIndex < 0) {
                console.warn("Visual row not found for csrId:", csrId);
                return;
            }

            // Step 4: Apply updates to visible table
            Object.entries(updatedFields).forEach(([field, value]) => {
                if (!field || typeof field !== 'string') return;

                const columnExists = hot.getSettings().columns.some(col => col.data === field);
                if (!columnExists) return;

                isApplyingServerUpdate = true;
                hot.setDataAtRowProp(visualRowIndex, field, value);
                isApplyingServerUpdate = false;
            });
            },
            error: xhr => {
            console.error("Save error:", xhr.responseText);
            alert("Error saving changes.");
            }
        });
        }
})();