(function($) {
    $(document).on('dt:engine-ready', function(event, tableApi) {
        const state = window.CardLiveFeedState;
        const grid = $('#visual-card-grid');

        // Hook table draw iterations to sequence structural grid modifications
        tableApi.on('draw.dt', function() {
            const actualIdx = state.idxId;
            grid.find('.card-item').hide();
            
            const currentPageIds = tableApi.rows({ page: 'current', filter: 'applied', order: 'applied' })
                                           .data().toArray().map(row => row[actualIdx] ? row[actualIdx].toString() : '');

            currentPageIds.forEach(id => { 
                grid.find(`.card-item[data-id="${id}"]`).show().appendTo(grid); 
            });

            sessionStorage.setItem('card_sequence', JSON.stringify(currentPageIds));
            
            setTimeout(() => { 
                grid.removeClass('filtering-active');
                $('.dtsp-searchPane').removeClass('pane-processing');
                if (typeof loadingNextPage !== 'undefined' && !loadingNextPage) $('#infinite-loader').hide(); 
            }, 150);
        });

        // --- 3-STATE RADIO TOGGLE MECHANICS ---
        const $toggleContainer = $('<div class="view-toggle-group"></div>').css({
            'display': 'flex', 'gap': '5px', 'background': '#eee', 'padding': '3px', 'border-radius': '6px'
        });
        
        ['Grid', 'Table', 'Grouped'].forEach((view, idx) => {
            const $radio = $(`<input type="radio" name="view-toggle" id="view-${idx}" value="${idx}" ${idx === 0 ? 'checked' : ''} style="display:none;">`);
            const $label = $(`<label for="view-${idx}" style="padding: 6px 12px; cursor: pointer; font-size: 12px; font-weight: 600; border-radius: 4px; transition: 0.2s;">${view}</label>`);
            if (idx === 0) $label.css({'background': '#fff', 'box-shadow': '0 1px 3px rgba(0,0,0,0.1)'});

            $label.on('click', function() {
                $('.view-toggle-group label').css({'background': 'transparent', 'box-shadow': 'none'});
                $(this).css({'background': '#fff', 'box-shadow': '0 1px 3px rgba(0,0,0,0.1)'});
                
                const $engineTable = $('#card-data-engine');
                const $groupedView = $('#grouped-card-view');

                $engineTable.attr('style', 'display: none !important;');
                grid.hide(); $groupedView.hide();

                if (idx === 0) grid.show();
                else if (idx === 1) $engineTable.attr('style', 'display: table !important; width: 100%; margin-top: 20px;');
                else if (idx === 2) $groupedView.show();
                
                if (typeof renderCheckboxUI === 'function') renderCheckboxUI();
            });
            $toggleContainer.append($radio).append($label);
        });
        $('#header-toggle-mount').append($toggleContainer);

        // --- LIVE IMAGE PREVIEW TRACKING HOVERS ---
        $('#card-data-engine tbody').on('mouseenter', 'tr', function() {
            const rowData = tableApi.row(this).data();
            if (!rowData) return;

            const urlFront = rowData[state.idxFrontHdUrl] ? rowData[state.idxFrontHdUrl].trim() : '';
            const urlBack = rowData[state.idxReverseHdUrl] ? rowData[state.idxReverseHdUrl].trim() : '';
            let hasValidImage = false;

            if (urlFront && urlFront !== 'None' && urlFront !== '-') {
                $('#preview-front').attr('src', urlFront).show(); hasValidImage = true;
            } else { $('#preview-front').hide(); }

            if (urlBack && urlBack !== 'None' && urlBack !== '-') {
                $('#preview-back').attr('src', urlBack).show(); hasValidImage = true;
            } else { $('#preview-back').hide(); }

            if (hasValidImage) $previewBox.show();
        })
        .on('mousemove', 'tr', function(e) {
            $previewBox.css({ top: (e.clientY + 15) + 'px', left: (e.clientX + 15) + 'px' });
        })
        .on('mouseleave', 'tr', function() {
            $previewBox.hide();
            $('#preview-front').attr('src', ''); $('#preview-back').attr('src', '');
        });

        // --- DUAL RESOLUTION SWAP ENGINE ---
        $('#card-data-engine tbody').on('click', 'img', function (e) {
            e.stopPropagation();
            const $clickedImg = $(this);
            const $row = $clickedImg.closest('tr');
            const rowData = tableApi.row($row).data();
            if (!rowData) return;

            $row.toggleClass('expanded-row');
            const isExpanded = $row.hasClass('expanded-row');
            const $frontImg = $row.find(`td:eq(${state.idxFrontUrl}) img, img.lazy-table-img:eq(0)`).first();
            const $reverseImg = $row.find(`td:eq(${state.idxReverseUrl}) img, img.lazy-table-img:eq(1)`).first();

            if (!$frontImg.data('thumb')) $frontImg.data('thumb', $frontImg.attr('src'));
            if (!$reverseImg.data('thumb')) $reverseImg.data('thumb', $reverseImg.attr('src'));

            if (isExpanded) {
                const lazyLoadAsset = ($el, url) => {
                    if (!url || url === '-' || url === 'None') return;
                    const imgCache = new Image();
                    imgCache.onload = () => { $el.data('current-hd', url).attr('src', url); };
                    imgCache.src = url;
                };
                lazyLoadAsset($frontImg, rowData[state.idxFrontHdUrl]);
                lazyLoadAsset($reverseImg, rowData[state.idxReverseHdUrl]);
            } else {
                $frontImg.attr('src', $frontImg.data('thumb'));
                $reverseImg.attr('src', $reverseImg.data('thumb'));
            }
        });

        // SearchPane Interactions Updates Interceptor
        $('#panes-container').on('click', '.dtsp-searchPane table tbody tr', function() {
            $(this).toggleClass('selected'); 
            grid.addClass('filtering-active');
            $(this).closest('.dtsp-searchPane').addClass('pane-processing');
            if (typeof loader !== 'undefined') loader.text("Applying filters...").show();
        });
    });
})(jQuery);