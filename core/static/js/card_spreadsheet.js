const SpreadsheetModule = (function() {
    let hotInstance = null;
    let isApplyingServerUpdate = false;

    // --- Private Renderers ---
    function imageRenderer(instance, td, row, col, prop, value, cellProperties) {
        td.innerHTML = '';
        if (value) {
            const img = document.createElement('img');
            img.src = value;
            img.style.width = '40px';
            img.style.height = 'auto';
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
                const isImage = header.toLowerCase() === 'front' || header.toLowerCase() === 'reverse';
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
                    rowHeaders: true,
                    height: '70vh',
                    stretchH: 'all',
                    filters: true,
                    dropdownMenu: true,
                    licenseKey: 'non-commercial-and-evaluation',
                    
                    afterChange: (changes, source) => {
                        if (source === 'loadData' || isApplyingServerUpdate) return;
                        
                        changes.forEach(([visualRow, prop, oldValue, newValue]) => {
                            if (oldValue === newValue) return;
                            
                            const update = {};
                            update[prop] = newValue;
                            this.syncToServer(visualRow, update);
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
})();