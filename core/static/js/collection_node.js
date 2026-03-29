
  window.submitCardForm = function(collectionId, cardId, targetUrl) {
    const visibleCards = document.getElementById(`visible-cards-${collectionId}`);
    let cardIds = [];

    if (visibleCards && visibleCards.value) {
      try {
        cardIds = JSON.parse(visibleCards.value).map(Number);
      } catch (e) {
        console.warn("Invalid JSON in visibleCards:", e);
      }
    }

    const form = document.getElementById(`view-card-form-${cardId}`);
    form.action = targetUrl;
    visibleCards.value = JSON.stringify(cardIds);  // ensure value is set
    form.submit();
  };


function handleDrop(event, collectionId) {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        uploadImage(collectionId, files);
    }
}

function handlePaste(event, collectionId) {
    const items = event.clipboardData.items;
    const files = [];
    for (const item of items) {
        if (item.kind === "file") {
            files.push(item.getAsFile());
        }
    }
    if (files.length > 0) {
        uploadImage(collectionId, files);
    }
}

  
function submitCollection(url) {
    console.log("here");
    launchSequence()
    // 1. Get the data
    const rawData = sessionStorage.getItem('card_sequence');
    const selections = rawData ? JSON.parse(rawData) : [];
    
    console.log("Sending IDs to backend:", selections);

    $.ajax({
      url: url,
      method: "POST", // Change to POST
      data: {
          'card_ids': selections, // Selections is your [3691, 3692, ...]
      },
      success: function(response) {
          if (response.success) {
              location.reload();
          } else {
              alert("Server error: " + response.error);
          }
      },
      error: function(xhr) {
          // Since you got a 500 error, this block will now catch it
          console.log(xhr.responseText); 
          alert("Request failed. Check the Django terminal for the traceback.");
      }
  });
}

function updateAttributeVisibility() {
  const selected = Array.from(document.querySelectorAll('.attr-toggle:checked'))
    .map(cb => cb.value);

  document.querySelectorAll('[data-attr]').forEach(el => {
    const attr = el.getAttribute('data-attr');
    el.style.display = selected.includes(attr) ? '' : 'none';
  });
}

// Initial render
updateAttributeVisibility();

// Re-run on checkbox change
document.querySelectorAll('.attr-toggle').forEach(cb => {
  cb.addEventListener('change', updateAttributeVisibility);
});

function toggleAttributePanel() {
  const panel = document.getElementById("attributePanel");
  panel.style.display = panel.style.display === "none" ? "block" : "none";
}

function getSelectedAttributes() {
  const checkboxes = document.querySelectorAll(".attr-toggle");
  return Array.from(checkboxes)
    .filter(cb => cb.checked)
    .map(cb => cb.value);
}

function filterCards(statusClass, element) {
    const allCards = document.querySelectorAll('.card-item:not(.folder)');
    const allButtons = document.querySelectorAll('.filter-btn');

    // 1. Handle Button Active States
    allButtons.forEach(btn => btn.classList.remove('active'));
    if (statusClass !== 'all') {
        element.classList.add('active');
    }

    // 2. Filter the Cards
    allCards.forEach(card => {
        if (statusClass === 'all') {
            card.classList.remove('hidden-card');
        } else {
            // Check if the card has the specific status class
            if (card.classList.contains(statusClass)) {
                card.classList.remove('hidden-card');
            } else {
                card.classList.add('hidden-card');
            }
        }
    });

    // 3. Update a "Results Found" count (Optional)
    const visibleCount = document.querySelectorAll('.card-item:not(.hidden-card):not(.folder)').length;
    console.log(`Showing ${visibleCount} cards`);
}

function sortCardsInModule(selectEl) {
  // Traverse up to the nearest .collection container
  const container = selectEl.closest('.collection');
  if (!container) {
    console.warn('No collection container found for sorting');
    return;
  }
  
  const collectionId = container.id.split('-')[1];
  const cardList = container.querySelector('.card-list');
  if (!cardList) {
    console.warn('No card list found in collection');
    return;
  }

  const cards = Array.from(cardList.querySelectorAll('.card'));

  // Exclude the last item (e.g. add-controls)
  const lastItem = cardList.lastElementChild;
  const sortableCards = cards.filter(card => card !== lastItem);

  const key = selectEl.value;
  sortableCards.sort((a, b) => {
    const aData = a.querySelector('.card-item')?.dataset || {};
    const bData = b.querySelector('.card-item')?.dataset || {};

    const aVal = aData[key] || '';
    const bVal = bData[key] || '';

    if (key === 'search_count') {
      return parseInt(bVal) - parseInt(aVal);
    }
    return aVal.localeCompare(bVal);
  });

  // Reflow sorted cards
  sortableCards.forEach(card => cardList.appendChild(card));
  if (lastItem) cardList.appendChild(lastItem); // Preserve final control
}


function filterCardsInModule(selectEl, collectionId) {
  const container = document.getElementById(`collection-${collectionId}`);
  if (!container) {
    console.warn('No collection container found for filtering');
    return;
  }

  const cardList = container.querySelector('.card-list');
  if (!cardList) {
    console.warn('No card list found in collection');
    return;
  }

  const cards = Array.from(cardList.querySelectorAll('.card'));
  console.log(cards)
  const lastItem = cardList.lastElementChild;
  const selectedOption = selectEl.selectedOptions?.[0];
  console.log("Selected option:", selectedOption);
  const key = selectedOption?.value ?? '';
  console.log("collectionId:", collectionId);
  const filterValue = selectedOption?.text ?? '';

  console.log("Filtering by:", key, filterValue, collectionId);

  const visibleCardIds = [];

  cards.forEach(card => {
    if (card === lastItem) {
      card.style.display = ''; // Always show control element
      return;
    }

    const data = card.querySelector('.card-item')?.dataset || {};
    const val = data[key] || '';

    const isMatch = filterValue === ''
      || (key === 'search_count'
          ? parseInt(val) === parseInt(filterValue)
          : val === filterValue);

    card.style.display = isMatch ? '' : 'none';

    if (isMatch && data.id) {
      visibleCardIds.push(data.id);
    }
  });

  // Update hidden input with visible card IDs
  updateSelection(collectionId)
}

function updateSelection(collectionId) {
  const checkboxes = document.querySelectorAll('input[name="selected_cards"]:checked');
  const hiddenInput = document.getElementById(`visible-cards-`+collectionId);
  const selectedIds = Array.from(checkboxes).map(cb => cb.value);
  if (hiddenInput) {
    hiddenInput.value = JSON.stringify(selectedIds);
    console.log("Updated visible_cards input:", selectedIds);
  }
}

function triggerFileUpload(elementId) {
  document.getElementById(elementId).click();
}

function uploadImage(collectionId, files) {
  if (!files || files.length === 0) return;

  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append("images", files[i]); // Django expects 'images' as a list
  }
  formData.append("collection_id", collectionId);

  fetch("/upload_image/", {
    method: "POST",
    body: formData,
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      location.reload(); // or dynamically insert new cards
    } else {
      alert("Upload failed: " + data.message);
    }
  });
}

function uploadSlab(collectionId, files) {
  if (!files || files.length === 0) return;

  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append("images", files[i]); // Django expects 'images' as a list
  }
  formData.append("collection_id", collectionId);
  formData.append("slab", true);

  fetch("/upload_image/", {
    method: "POST",
    body: formData,
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      location.reload(); // or dynamically insert new cards
    } else {
      alert("Upload failed: " + data.message);
    }
  });
}

function getCSRFToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function toggleChildren(el) {
  const node = el.closest('.collection-node');
  const subs = node.querySelector('.subcollections');
  subs.style.display = subs.style.display === 'none' ? 'block' : 'none';
  el.textContent = subs.style.display === 'none' ? '▶' : '▼';
}

function addCard(collectionId) {
  // AJAX call to Django view to create a new card
  console.log("Add card to collection:", collectionId)
  window.location.href = "/upload_image/" + collectionId;
}

function openForAutomaticInput(collectionId) {
  fetch(`/set_default_collection/${collectionId}`);
}

function addSubcollection(parentId) {
  // AJAX call to create nested collection
  $.post("/collection_create/", {
        collection_id: parentId
    }, function(response) {
        if (response.error) {
            alert("Error: " + response.message);
        } else {
            location.reload()
        }
    });
}

function removeCard(cardId) {
  // AJAX call to delete card
  $.post("/delete/", {
        card_id: cardId,
    }, function(response) {
        if (response.error) {
            alert("Error: " + response.message);
        } else {
            location.reload()
        }
    });
}

function toggleMoveDropdown(cardId) {
  const dropdown = document.getElementById('move-card-' + cardId);
  dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
}

function toggleMoveCollectionDropdown(collectionId) {
  const dropdown = document.getElementById('move-collection-' + collectionId);
  dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
}

function refreshCollectionCount(collectionId) {
  const container = document.querySelector(`#collection-${collectionId}`);
  const cardList = container?.querySelector('.card-list');
  if (!cardList) return;

  const count = Array.from(cardList.children).filter(child =>
    child.classList.contains('card')
  ).length;

  const countSpan = document.querySelector(`#card-count-${collectionId}`);
  if (countSpan) {
    countSpan.textContent = count;
  }
}

function moveToCollection(cardId, collectionToMoveId, targetCollectionId) {
  let selectedCardIds;
  const visibleCards = document.getElementById(`visible-cards-${collectionToMoveId}`).value;
  if (visibleCards)
    selectedCardIds = JSON.parse(visibleCards).map(Number);
  else
    selectedCardIds = ""
  const initiatingCardId = cardId

  //if I have an initiating cardid and no visibleCards, move the single card to the targetcollection
  //if initiatingCardId is none, this will fall through to collection-collection 
  if ((selectedCardIds == "") || (selectedCardIds == "[]"))
    selectedCardIds = [initiatingCardId]

  fetch('/move_to_collection/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      //'X-CSRFToken': getCookie('csrftoken')  // Make sure you have a getCookie() helper
    },
    body: JSON.stringify({
      collection_to_move: collectionToMoveId,      
      cards_to_move:selectedCardIds,
      target_collection: targetCollectionId,
    })
  })
  .then(response => {
    console.log("Successfully");
    location.reload()
  })
  .catch(err => {
    console.error("❌ Error sending data:", err);
  });
}

function toggleMoveMenu(event, cardId) {
    event.preventDefault();
    event.stopPropagation();
    
    // Close any other open menus first
    document.querySelectorAll('.move-menu').forEach(menu => {
        if (menu.id !== `dropdown-${cardId}`) menu.style.display = 'none';
    });

    const menu = document.getElementById(`dropdown-${cardId}`);
    menu.style.display = (menu.style.display === 'block') ? 'none' : 'block';
}

// Close dropdowns if user clicks anywhere else on the page
window.onclick = function(event) {
    if (!event.target.matches('.nav-button')) {
        document.querySelectorAll('.move-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    }
};

function moveCardToCollection(cardId, collectionId) {
    
  const menu = document.getElementById(`dropdown-${cardId}`);
  if (menu) menu.style.display = 'none';
  launchSequence()
  // 1. Get the current selection (if any). Fallback to the single cardId.
    const rawSeq = sessionStorage.getItem('card_sequence');
    const selections = rawSeq ? JSON.parse(rawSeq) : [cardId];
    console.log(selections, collectionId)
    
    fetch(`/move_to_collection/${collectionId}/`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            card_ids: selections
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Move failed');
        return response.json();
    })
    .then(data => {
        // 3. remove each card in the DOM
        selections.forEach(id => {
            const cardElement = document.querySelector(`#card-${id}`);
            cardElement.remove();
        });

        // 4. Refresh count for the new container (only once)
        refreshCollectionCount(collectionId);
        
        // 5. Clear sequence after a successful move
        sessionStorage.removeItem('card_sequence');
        
        if (event && event.target) restoreButton(event.target);
    })
    .catch(error => {
        console.error('Error moving cards:', error);
        if (event && event.target) restoreButton(event.target);
    });
}
function removeCollection(collectionId) {
  // AJAX call to delete card
  $.post("/delete/", {
        collection_id: collectionId,
    }, function(response) {
        if (response.error) {
            alert("Error: " + response.message);
        } else {
            location.reload()
        }
    });
}

function searchCollection(collectionId) {
  const container = document.getElementById(`collection-${collectionId}`);
  if (!container) {
    console.warn("No collection found with ID:", collectionId);
    return;
  }

  console.log(visibleCards);
  const encodedIds = encodeURIComponent(visibleCards.join(','));
  const url = `/crop_review/${collectionId}?card_ids=${encodedIds}`;

  fetch(`/image_search_collection/${collectionId}/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ cards: visibleCards })
});



}
function saveCollectionField(collectionId, fieldName, fieldValue) {
  console.log("Saving field:", fieldName, "for collection:", collectionId);

  $.post("/update_collection/", {
    collectionId: collectionId,
    field: fieldName,
    value: fieldValue
  }, function(response) {
    if (response.error) {
      alert("Error: " + response.message);
      return;
    }

    // ✅ Update DOM based on which field was changed
    if (fieldName === "name") {
      // Update the visible title
      $(".collection-title[data-id='" + collectionId + "'] h2")
        .text(collectionId + ". " + fieldValue);

      // Clear the input field if it exists
      $("input[name='collection_name_" + collectionId + "']").val("");
    }

    if (fieldName === "status") {
      // Update status UI (radio buttons)
      $("input[name='status-" + collectionId + "'][value='" + fieldValue + "']")
        .prop("checked", true);
    }

    // Add more fields here as needed
  });
}


function cropCard(collectionId, cardId) {
    window.location.href = "/crop_review/"+collectionId
    const cardIds = JSON.parse(cardId).map(Number);
}

function cropCollection(collectionId) {
  const visibleCards = document.getElementById(`visible-cards-${collectionId}`);
  const cardIds = JSON.parse(visibleCards.value).map(Number);
  window.location.href = "/crop_review/"+collectionId
}

function loadReverse(wrapper) {
    const hoverImg = wrapper.querySelector('.thumbnail.hover');
    
    // Only set the src if it hasn't been loaded yet
    if (hoverImg && !hoverImg.src && hoverImg.dataset.src) {
        hoverImg.src = hoverImg.dataset.src;
        
        // Optional: Remove the data-src once loaded to keep DOM clean
        hoverImg.removeAttribute('data-src');
    }
}