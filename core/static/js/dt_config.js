window.CardLiveFeedState = {
    isProcessingQueue: false,
    isApplyingServerUpdate: false,
    quickEditQueue: [],
    quickEditDebounceTimer: null,
    selectedIds: new Set(),
    activeFocusLock: null,
    
    // Header tracking map and baseline fallbacks
    headerMap: {}, 
    idxId: 14, 
    idxCsrId: 1, 
    idxFrontUrl: 4, 
    idxReverseUrl: 5, 
    idxFrontHdUrl: 15, 
    idxReverseHdUrl: 16
};

// Global Tooltip DOM Cache Element
const $previewBox = $('<div id="live-card-preview" style="position:fixed; display:none; z-index:9999; pointer-events:none; background:#fff; border:1px solid #ccc; padding:5px; border-radius:4px; box-shadow:0 2px 8px rgba(0,0,0,0.15);"><img id="preview-front" style="max-height:350px; margin-right:5px; display:none;"><img id="preview-back" style="max-height:350px; display:none;"></div>');
$(() => $('body').append($previewBox));

function createPersistentInputRenderer(data) {
    const val = data !== null ? String(data).replace(/"/g, '&quot;') : '';
    return `<input type="text" class="dt-inline-edit" value="${val}" data-current="${val}">`;
}

function createImageRenderer(data) {
    if (!data || data === '-' || data === 'None') return `<span class="text-muted">-</span>`;
    return `<img src="${data}" class="lazy-table-img" style="height:40px; border-radius:3px; cursor:pointer;">`;
}