$(document).ready(function () {
    
  document.querySelectorAll(`input[type='text'][id^='title_to_be']`).forEach(input => {
    csrState = `{{ search_result.status }}`
    console.log("stat: ",csrState)
    if (csrState == "new") 
      console.log("new csr")
      rebuildTitle(input); // Run once on init
  });
  
    $(document).on("click", ".clearGroupBtn", function () {
      console.log("Clear group clicked!");
      const cardId = this.dataset.cardId;
      const csrId = this.dataset.csrId;

      console.log("cid", cardId);

      const allFields = collectAllFields(cardId);
      allFields.group_key = "";

      $.ajax({
      url: "/update_csr_fields/",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({
          csrId: csrId,
          allFields: allFields,
      }),
      headers: { "X-CSRFToken": "{{ csrf_token }}" }
  });
});

  
  // 🧩 Allow HTML in autocomplete labels
  $.ui.autocomplete.prototype._renderItem = function (ul, item) {
    if (item.isDivider) {
      return $("<li>")
        .addClass("autocomplete-divider")
        .append("<hr style='margin:4px 0;'>")
        .appendTo(ul);
    }

    const li = $("<li>")
      .addClass(item.disabled ? "autocomplete-disabled" : "")
      .append($("<div>").text(item.label));

    return li.appendTo(ul);
  };
  // 🗂️ Initialize saved values
  const savedValues = {};
  $("input[type='text']").each(function () {
    let name = $(this).attr("name");
    const value = $(this).val();

    if (name && name.endsWith("_m")) {
      name = name.slice(0, -2);
    }

    if (name) {
      if (!savedValues[name]) {
        savedValues[name] = new Set();
      }
      savedValues[name].add(value);
    }
  });
  

  // 💾 Save button handler
  $("#saveFieldsBtn").on("click", function () {
    let cardId = "{{ card_id }}"
    console.log("cid", cardId)
    const allFields = collectAllFields(cardId);

    console.log("Payload:", {
      csrId: "{{ search_result.id }}",
      ...allFields,
      csrfmiddlewaretoken: '{{ csrf_token }}'
    });

    $.ajax({
      url: "/update_csr_fields/",
      method: "POST",
      data: {
        csrId: "{{ search_result.id }}",
        ...allFields,
        csrfmiddlewaretoken: '{{ csrf_token }}'
      },
      success: response => {
        console.log("Saved:", response);
        alert("Changes saved successfully.");
      },
      error: xhr => {
        console.error("Save error:", xhr.responseText);
        alert("Error saving changes.");
      }
    });
  });
});



function updateCharCount(input) {
    const maxLength = 80;
    const currentLength = input.value.length;

    if (currentLength >= maxLength) {
        // Red highlight
        input.style.borderColor = "#ff4d4d";
        input.style.boxShadow = "0 0 5px rgba(255, 77, 77, 0.5)";
        input.style.outline = "none";
    } else {
        // Return to default
        input.style.borderColor = "#ccc";
        input.style.boxShadow = "none";
    }
}

function collectAllFields(cardId, required_only = false) {
  console.log(`collectAllFields called for cardId=${cardId}, required_only=${required_only}`);
  const allFields = {};
  //console.log(cardId)  
  //console.log("1", allFields)
  // Checkboxes
  document.querySelectorAll(`input[type='checkbox'][id$='-${cardId}']`).forEach(checkbox => {
    console.log("checkbox loop")
    let name = checkbox.name;
    const value = checkbox.checked

    if (name && name.endsWith(`_${cardId}`)) {
      name = name.slice(0, -(`_${cardId}`.length));
    }

    if (required_only) {
      if (!name.startsWith('attributes') && value) {  
        allFields[name] = value;
      }
    }
    else {
        allFields[name] = value;
    }
  });
  //console.log("2", allFields)
  // Text inputs
  document.querySelectorAll(`input[type='text'][id$='-${cardId}'], textarea[id$='-${cardId}']`).forEach(el => {
    console.log("textbox loop")
    let name = el.name;
    //console.log(el.name)
    const value = el.value;

    if (name && name.endsWith("_m")) {
      name = name.slice(0, -2);
    }
    if (name && name.endsWith(`-${cardId}`)) {
      name = name.slice(0, -(`-${cardId}`.length));
    }

    // If required_only is true, skip non checked fields
    is_required = allFields[`${name}_is_manual`] || false;
    if (required_only && name && !is_required) {
      return;
    }

    if (name) {
      allFields[name] = value;
    }
  });
  
  //why the fuck is this here?
  //console.log("3", allFields)
  document.querySelectorAll(".calculated-input").forEach(input => {
    console.log(".calculated-input loop")
    input.addEventListener("input", function () {
      const maxLength = parseInt(this.dataset.maxlength, 10);
      if (this.value.length > maxLength) {
        this.classList.add("input-error");
      } else {
        this.classList.remove("input-error");
      }
    });
  });
  //console.log("4", allFields)
  return allFields;
}

function handleSelect(selector, event, ui) {
  const selectedValue = selector.value;
  console.log("Selected value:", selector);
  // You can add more logic here to handle the selected value
  
  //console.log("Selected item:", ui.item);
  const match = selector.match(/^#field_(.+)-(\d+)$/);
  if (!match) {
    console.warn("Unexpected field ID format:", selector);
    return;
  }

  const fieldName = match[1];
  const cardId = match[2];
  //console.log("fieldName", fieldName)
  const inputValue = $(selector).val(); // current text box value

  //console.log(cardId);
  //console.log("dan", ui);
    // If selected item is disabled, fallback to input value

  if (ui.item.disabled) {
    console.log("Disabled item selected, using input value:", inputValue);
    ui.item.value = "__add__";
    //rebuildTitle(fieldName, cardId);
    //return false;
  }
  rebuildTitle(fieldName, cardId);
  return false;
}


// Enable/disable field on checkbox toggle
function handleOverrideToggle(fieldName, cardId, csrId, isCheckboxDirect) {
  console.log("handle override", isCheckboxDirect)
  const checkbox = document.getElementById(`${fieldName}_is_manual-${cardId}`);
  const input = document.getElementById(`field_${fieldName}-${cardId}`);

  if (isCheckboxDirect) {
    if (checkbox.checked) {
      input.removeAttribute("readonly");
    } else {
      input.setAttribute("readonly", "readonly");
      const defaultValue = input.getAttribute("data-default");
    }
    handleEnterPress(fieldName, cardId, csrId)
  } else {
    //only want to handle this to turn ON the field
    if (!checkbox.checked) {
      input.removeAttribute("readonly");
      checkbox.checked = true;
      //don't need the enter press because the click puts us in
    }
  }
}

function rebuildTitle(fieldName, cardId) {
  console.log(`rebuildTitle called with field="${fieldName}", idx=${cardId}`);

  const titleFieldId = `field_title_to_be-${cardId}`;
  const thisFieldId = `${fieldName}-${cardId}`;
  console.log("titleFieldId:", titleFieldId);
  console.log("thisFieldId:", thisFieldId);

  if (titleFieldId !== `field_${thisFieldId}`) {
    const titleCheckbox = document.getElementById(`title_to_be_is_manual-${cardId}`);
    const titleElement = document.getElementById(titleFieldId);

    if (titleElement) {// && !titleCheckbox.checked) {
      // ⏳ Delay field collection until DOM updates
      setTimeout(() => {
        const fields = collectAllFields(cardId);
        console.log("Collected fields2:", fields);

        // #this is a re-implementation of csr.build_title
        const titleParts = [
          fields.year,
          fields.brand,
          fields.subset !=" " ? `${fields.subset}` : null,
          fields.full_name,
          fields.parallel !=" " ? `${fields.parallel}` : null,
          fields.card_name !="" ? `${fields.card_name}` : null, 
          fields.card_number != "" ? `#${fields.card_number}` : null,
          fields.city,
          fields.team,
          fields.condition,
          fields["attributes.Oddball"] ? "Oddball" : null
        ];

      titleElement.value = titleParts
        .filter(part => part && part.trim() !== '') // Remove null/empty/whitespace-only
        .join(' ');

        //titleElement.value = `${fields.year} ${fields.brand} ${fields.subset} ${fields.full_name} ${fields.serial_number} #${fields.card_number} ${fields.city} ${fields.team}`;

      }, 0);
    } else {
      console.log("No title element or checkbox is checked.");
    }
  }
  
  const titleElement = document.getElementById(titleFieldId);
  const maxLength = parseInt(titleElement.dataset.maxlength, 10);
  if (titleElement.value.length > maxLength) {
    titleElement.classList.add("input-error");
  } else {
    titleElement.classList.remove("input-error");
  }
} 

//TODO:this needs to be combined with quickedit on spreadsheet.html
let debounceTimers = {};

function handleEnterPress(fieldName, cardId, csrId) {
  const key = `${fieldName}-${cardId}`;
  clearTimeout(debounceTimers[key]);

  debounceTimers[key] = setTimeout(() => {
    const inputId = `field_${fieldName}-${cardId}`;
    const inputEl = document.getElementById(inputId);
    let value = inputEl?.value;
    console.log("handle Enter:", inputEl);
    if (!inputEl) {
      console.warn(`Input element not found for ${inputId}`);
      return;
    }
    if (fieldName.startsWith("attrib")) {
      fieldName = fieldName.replace("-", ".");
      value = inputEl.checked;
    } else {
      inputEl.blur();
    }

    const brandInput = document.getElementById(`field_brand-${cardId}`);
    const cityInput = document.getElementById(`field_city-${cardId}`);

    const brand = brandInput?.value || "";
    const city = cityInput?.value || "";

    const brandChanged = brandInput?.disabled === false;
    const cityChanged = cityInput?.disabled === false;

    const fields = {
      [fieldName]: value,
      [`${fieldName}_is_manual`]: true,
      brand: brand,
      brand_is_manual: brandChanged,
      city: city,
      city_is_manual: cityChanged
    };

    $.ajax({
      url: "/update_csr_fields/",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({
        csrId: csrId,
        allFields: fields
      }),
      success: response => {
        const updatedFields = response.search_result;
        console.log("✅ Server response:", updatedFields);

        Object.entries(updatedFields).forEach(([key, val]) => {
          const fieldInput = document.getElementById(`field_${key}-${cardId}`);
          const manualCheckbox = document.getElementById(`${key}_is_manual-${cardId}`);

          if (fieldInput) {
            if ((fieldInput.tagName === "TEXTAREA" || fieldInput.type === "text")
                && (!manualCheckbox || !manualCheckbox.checked)) {
              fieldInput.value = val;
            } 
          }
        });
      },
      error: xhr => {
        console.error("❌ Save error:", xhr.responseText);
        alert("Error saving changes.");
      }
    });
  }, 300); // debounce delay in ms
}

// ❌ Clear Group handler
$(".clearGroupBtn").on("click", function () {
    
});
