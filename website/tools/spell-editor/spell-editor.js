const spellGrid = document.getElementById("spell-grid");
const spellSlots = spellGrid
  ? Array.from(spellGrid.querySelectorAll(".spell-grid-slot"))
  : [];
const spellTitle = document.getElementById("spell-title");
const spellPrev = document.getElementById("spell-prev");
const spellNext = document.getElementById("spell-next");
const spellDots = document.getElementById("spell-dots");
const bookPrev = document.getElementById("book-prev");
const bookNext = document.getElementById("book-next");
const bookDots = document.getElementById("book-dots");
const bookTitle = document.getElementById("spellbook-title");
const spellSlotsRadial = Array.from(document.querySelectorAll(".spell-slot"));
const spellSlotContents = Array.from(
  document.querySelectorAll(".spell-slot__content")
);
const tooltip = document.getElementById("tooltip");
const tooltipName = document.getElementById("tooltip-name");
const tooltipDesc = document.getElementById("tooltip-desc");
const tooltipMeta = document.getElementById("tooltip-meta");
const statusBar = document.querySelector(".status-bar");
const statusIcon = document.querySelector(".status-bar__icon");
const statusText = document.getElementById("status-text");
const loadButton = document.getElementById("load-button");
const saveButton = document.getElementById("save-button");
const characterInput = document.getElementById("character-file");
const contextMenu = document.getElementById("spell-context-menu");

const SPELLS_URL = "/tools/spell-editor/data/spells.json";
const ICONS_BASE = "/shared/icons/";
const SPELLS_PER_PAGE = 40;
const SPELLS_PER_BOOK = 12;
const SPELLBOOK_COUNT = 4;
const SLOT_OFFSET = 0;

let spells = [];
let spellMap = new Map();
let browserPage = 0;
let bookPage = 0;
let selectedSpells = Array(48).fill("");
let characterSource = null;
let characterFileName = null;
let characterFileHandle = null;
let contextSlotIndex = null;

function getAbsoluteIndex(slotIndex) {
  const adjustedIndex =
    (slotIndex - SLOT_OFFSET + SPELLS_PER_BOOK) % SPELLS_PER_BOOK;
  return bookPage * SPELLS_PER_BOOK + adjustedIndex;
}

function iconPath(iconName) {
  if (!iconName) {
    return "";
  }
  return `${ICONS_BASE}${iconName}`;
}

function setStatus(message, loaded) {
  if (!statusText || !statusBar || !statusIcon) {
    return;
  }
  statusText.textContent = message;
  statusBar.classList.toggle("status-bar--loaded", loaded);
  statusBar.classList.toggle("status-bar--unloaded", !loaded);
  statusIcon.src = loaded
    ? "/shared/game-ui/Status/status_loaded_icon.png"
    : "/shared/game-ui/Status/status_unloaded_icon.png";
  if (saveButton) {
    saveButton.classList.toggle("hidden", !loaded);
  }
}

function updateSpellTitle() {
  if (!spellTitle) {
    return;
  }
  spellTitle.textContent = `All Spells (${spells.length})`;
}

function updateBookTitle() {
  if (!bookTitle) {
    return;
  }
  bookTitle.textContent = `Spellbook ${bookPage + 1}`;
}

function renderBrowser() {
  const start = browserPage * SPELLS_PER_PAGE;
  const pageItems = spells.slice(start, start + SPELLS_PER_PAGE);
  spellSlots.forEach((slot, idx) => {
    slot.innerHTML = "";
    slot.classList.remove("has-item");
    slot.removeAttribute("draggable");
    slot.removeAttribute("data-spell-index");
    const spell = pageItems[idx];
    if (!spell) {
      return;
    }
    slot.classList.add("has-item");
    slot.dataset.spellIndex = String(start + idx);
    slot.setAttribute("draggable", "true");
    const icon = document.createElement("img");
    icon.className = "item-icon";
    icon.src = iconPath(spell.spell_icon);
    icon.alt = "";
    slot.appendChild(icon);
    if (spell.spell_tag_icon) {
      const tag = document.createElement("img");
      tag.className = "spell-tag-icon";
      tag.src = iconPath(spell.spell_tag_icon);
      tag.alt = "";
      slot.appendChild(tag);
    }
  });
}

function updateBrowserPagination() {
  const pageCount = Math.max(1, Math.ceil(spells.length / SPELLS_PER_PAGE));
  const isFirst = browserPage === 0;
  const isLast = browserPage >= pageCount - 1;

  if (spellPrev) {
    spellPrev.classList.toggle("is-disabled", isFirst);
    const img = spellPrev.querySelector("img");
    if (img) {
      img.src = isFirst ? img.dataset.disabledSrc : img.dataset.enabledSrc;
    }
  }
  if (spellNext) {
    spellNext.classList.toggle("is-disabled", isLast);
    const img = spellNext.querySelector("img");
    if (img) {
      img.src = isLast ? img.dataset.disabledSrc : img.dataset.enabledSrc;
    }
  }

  if (!spellDots) {
    return;
  }
  spellDots.innerHTML = "";
  for (let i = 0; i < pageCount; i += 1) {
    const dot = document.createElement("img");
    dot.src =
      i === browserPage
        ? "/shared/game-ui/ItemBrowser/Current_Page_Dot.png"
        : "/shared/game-ui/ItemBrowser/Non_Selected_Page_Dot.png";
    dot.alt = i === browserPage ? "Current page" : "Page";
    dot.addEventListener("click", () => {
      browserPage = i;
      renderBrowser();
      updateBrowserPagination();
    });
    spellDots.appendChild(dot);
  }
}

function renderWheel() {
  spellSlotsRadial.forEach((slot) => {
    const index = Number(slot.dataset.slot);
    const absoluteIndex = getAbsoluteIndex(index);
    const spellId = selectedSpells[absoluteIndex] || "";
    const spell = spellMap.get(spellId);
    slot.classList.toggle("has-spell", Boolean(spell));
    slot.dataset.spellId = spellId;
    slot.dataset.absoluteIndex = String(absoluteIndex);
    if (spell) {
      slot.setAttribute("draggable", "true");
    } else {
      slot.removeAttribute("draggable");
    }
    const icon = slot.querySelector(".spell-slot__icon");
    const tag = slot.querySelector(".spell-slot__tag");
    if (icon) {
      icon.src = spell ? iconPath(spell.spell_icon) : "";
    }
    if (tag) {
      if (spell && spell.spell_tag_icon) {
        tag.src = iconPath(spell.spell_tag_icon);
        tag.classList.remove("hidden");
      } else {
        tag.removeAttribute("src");
        tag.classList.add("hidden");
      }
    }
  });
}

function updateBookPagination() {
  const isFirst = bookPage === 0;
  const isLast = bookPage >= SPELLBOOK_COUNT - 1;

  if (bookPrev) {
    bookPrev.classList.toggle("is-disabled", isFirst);
    const img = bookPrev.querySelector("img");
    if (img) {
      img.src = isFirst ? img.dataset.disabledSrc : img.dataset.enabledSrc;
    }
  }
  if (bookNext) {
    bookNext.classList.toggle("is-disabled", isLast);
    const img = bookNext.querySelector("img");
    if (img) {
      img.src = isLast ? img.dataset.disabledSrc : img.dataset.enabledSrc;
    }
  }

  if (!bookDots) {
    return;
  }
  bookDots.innerHTML = "";
  for (let i = 0; i < SPELLBOOK_COUNT; i += 1) {
    const dot = document.createElement("img");
    dot.src =
      i === bookPage
        ? "/shared/game-ui/ItemBrowser/Current_Page_Dot.png"
        : "/shared/game-ui/ItemBrowser/Non_Selected_Page_Dot.png";
    dot.alt = i === bookPage ? "Current book" : "Book";
    dot.addEventListener("click", () => {
      bookPage = i;
      updateBookTitle();
      renderWheel();
      updateBookPagination();
    });
    bookDots.appendChild(dot);
  }
}

function buildTooltip(spell) {
  if (!tooltip || !tooltipName || !tooltipDesc || !tooltipMeta || !spell) {
    return;
  }
  tooltipName.textContent = spell.display_name || "Spell";
  tooltipDesc.textContent = spell.requirements || "";
  tooltipMeta.innerHTML = "";

  if (spell.cooldown !== null && spell.cooldown !== undefined) {
    const row = document.createElement("div");
    row.className = "tooltip__row";
    const label = document.createElement("div");
    label.textContent = "Cooldown";
    const value = document.createElement("div");
    value.textContent = `${spell.cooldown}s`;
    row.appendChild(label);
    row.appendChild(value);
    tooltipMeta.appendChild(row);
  }

  const costs = spell.costs || [];
  if (costs.length) {
    costs.forEach((cost) => {
      const row = document.createElement("div");
      row.className = "tooltip__row";
      const iconWrap = document.createElement("div");
      iconWrap.className = "tooltip__icon";
      const icon = document.createElement("img");
      icon.src = iconPath(cost.icon);
      icon.alt = "";
      iconWrap.appendChild(icon);
      row.appendChild(iconWrap);
      const value = document.createElement("div");
      value.textContent = `${cost.display_name || cost.item_id} × ${cost.count}`;
      row.appendChild(value);
      tooltipMeta.appendChild(row);
    });
  }
}

function showTooltip(spell, event) {
  if (!tooltip) {
    return;
  }
  buildTooltip(spell);
  tooltip.classList.remove("hidden");
  onTooltipMove(event);
}

function hideTooltip() {
  if (!tooltip) {
    return;
  }
  tooltip.classList.add("hidden");
}

function onTooltipMove(event) {
  if (!tooltip) {
    return;
  }
  const offset = 16;
  tooltip.style.left = `${event.clientX + offset}px`;
  tooltip.style.top = `${event.clientY + offset}px`;
}

function findSpellcasting(data) {
  if (!data || typeof data !== "object") {
    return null;
  }
  if (Array.isArray(data)) {
    for (const item of data) {
      const found = findSpellcasting(item);
      if (found) {
        return found;
      }
    }
    return null;
  }
  if (Object.prototype.hasOwnProperty.call(data, "Spellcasting")) {
    return data.Spellcasting;
  }
  for (const value of Object.values(data)) {
    const found = findSpellcasting(value);
    if (found) {
      return found;
    }
  }
  return null;
}

function findProgress(data) {
  if (!data || typeof data !== "object") {
    return null;
  }
  if (Array.isArray(data)) {
    for (const item of data) {
      const found = findProgress(item);
      if (found) {
        return found;
      }
    }
    return null;
  }
  if (Object.prototype.hasOwnProperty.call(data, "Progress")) {
    return data.Progress;
  }
  for (const value of Object.values(data)) {
    const found = findProgress(value);
    if (found) {
      return found;
    }
  }
  return null;
}

function dedupeSpellIds(values) {
  return Array.from(new Set(values.filter((value) => value)));
}

function ensureSpellsUnlocked(progress, values) {
  if (!progress || typeof progress !== "object") {
    return;
  }
  const existing = Array.isArray(progress.SpellsUnlocked)
    ? progress.SpellsUnlocked
    : [];
  const unlocked = new Set(existing);
  const toAdd = values.filter((value) => value && !unlocked.has(value));
  if (toAdd.length || !Array.isArray(progress.SpellsUnlocked)) {
    progress.SpellsUnlocked = existing.concat(toAdd);
  }
}

function setSelectedSpells(data, values) {
  const spellcasting = findSpellcasting(data);
  if (!spellcasting || typeof spellcasting !== "object") {
    return false;
  }
  spellcasting.SelectedSpells = values;
  return true;
}

function buildExportData() {
  if (!characterSource) {
    return null;
  }
  const clone = JSON.parse(JSON.stringify(characterSource));
  const values = selectedSpells.slice(0, 48);
  const progress = findProgress(clone);
  if (progress && typeof progress === "object") {
    ensureSpellsUnlocked(progress, values);
  }
  if (!setSelectedSpells(clone, values)) {
    clone.Spellcasting = {
      SelectedSpells: values,
    };
  }
  if (!progress && typeof clone.Progress === "undefined") {
    clone.Progress = { SpellsUnlocked: dedupeSpellIds(values) };
  } else if (!progress && clone.Progress && typeof clone.Progress === "object") {
    ensureSpellsUnlocked(clone.Progress, values);
  }
  return clone;
}

function downloadJsonFile(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function saveCharacter() {
  const updated = buildExportData();
  if (!updated) {
    return;
  }
  const backupName = characterFileName
    ? characterFileName.replace(/\.json$/i, "") + "_backup.json"
    : "character_backup.json";
  const saveName = characterFileName ?? "character.json";

  if (characterFileHandle && "createWritable" in characterFileHandle) {
    try {
      const originalFile = await characterFileHandle.getFile();
      const originalText = await originalFile.text();
      const originalData = JSON.parse(originalText);
      downloadJsonFile(originalData, backupName);
      const writable = await characterFileHandle.createWritable();
      await writable.write(JSON.stringify(updated, null, 2));
      await writable.close();
      setStatus("Saved. Backup downloaded.", true);
      return;
    } catch (error) {
      setStatus("Save failed. Downloading files instead.", true);
    }
  }

  downloadJsonFile(updated, saveName);
  setStatus("Saved as download. Backup not written to disk.", true);
}

async function openCharacterFile() {
  if (window.showOpenFilePicker) {
    try {
      const [handle] = await window.showOpenFilePicker({
        types: [
          {
            description: "JSON Files",
            accept: { "application/json": [".json"] },
          },
        ],
      });
      const file = await handle.getFile();
      characterFileHandle = handle;
      characterFileName = file.name;
      const text = await file.text();
      handleCharacterFile(text);
      setStatus("Loaded via file picker. Save will overwrite this file.", true);
      return;
    } catch (error) {
      return;
    }
  }
  characterInput?.click();
}

function handleCharacterFile(text) {
  try {
    const data = JSON.parse(text);
    characterSource = data;
    const spellcasting = findSpellcasting(data);
    const values = spellcasting?.SelectedSpells || [];
    selectedSpells = Array(48)
      .fill("")
      .map((_, idx) => values[idx] || "");
    renderWheel();
    setStatus("Spellbook loaded.", true);
  } catch (error) {
    setStatus("Failed to parse character JSON.", false);
  }
}

function bindDragAndDrop() {
  spellSlots.forEach((slot) => {
    slot.addEventListener("dragstart", (event) => {
      const index = Number(slot.dataset.spellIndex);
      const spell = spells[index];
      if (!spell || !event.dataTransfer) {
        return;
      }
      event.dataTransfer.setData("text/plain", spell.persistence_id);
      const icon = slot.querySelector(".item-icon");
      if (icon && event.dataTransfer.setDragImage) {
        const size = 48;
        event.dataTransfer.setDragImage(icon, size / 2, size / 2);
      }
    });
  });

  spellSlotsRadial.forEach((slot) => {
    slot.addEventListener("dragover", (event) => {
      event.preventDefault();
      slot.classList.add("drag-allowed");
    });
    slot.addEventListener("dragleave", () => {
      slot.classList.remove("drag-allowed");
    });
    slot.addEventListener("drop", (event) => {
      event.preventDefault();
      slot.classList.remove("drag-allowed");
      const spellId = event.dataTransfer?.getData("text/plain");
      if (!spellId) {
        return;
      }
      const slotIndex = Number(slot.dataset.slot);
      const absoluteIndex = getAbsoluteIndex(slotIndex);
      selectedSpells[absoluteIndex] = spellId;
      renderWheel();
    });
    slot.addEventListener("dragstart", (event) => {
      const spellId = slot.dataset.spellId;
      if (!spellId || !event.dataTransfer) {
        return;
      }
      event.dataTransfer.setData("text/plain", spellId);
      event.dataTransfer.setData("source", "radial");
      event.dataTransfer.setData("absoluteIndex", slot.dataset.absoluteIndex || "");
      const icon = slot.querySelector(".spell-slot__icon");
      if (icon && event.dataTransfer.setDragImage) {
        const size = 48;
        event.dataTransfer.setDragImage(icon, size / 2, size / 2);
      }
    });
    slot.addEventListener("dragend", (event) => {
      if (event.dataTransfer?.dropEffect === "none") {
        const absoluteIndex = Number(slot.dataset.absoluteIndex);
        if (!Number.isNaN(absoluteIndex)) {
          selectedSpells[absoluteIndex] = "";
          renderWheel();
        }
      }
    });
  });
}

function openContextMenu(event, slotIndex) {
  if (!contextMenu) {
    return;
  }
  event.preventDefault();
  contextSlotIndex = slotIndex;
  contextMenu.style.left = `${event.clientX}px`;
  contextMenu.style.top = `${event.clientY}px`;
  contextMenu.classList.remove("hidden");
}

function closeContextMenu() {
  if (!contextMenu) {
    return;
  }
  contextMenu.classList.add("hidden");
  contextSlotIndex = null;
}

function bindEvents() {
  if (spellPrev) {
    spellPrev.addEventListener("click", () => {
      if (spellPrev.classList.contains("is-disabled")) {
        return;
      }
      browserPage = Math.max(0, browserPage - 1);
      renderBrowser();
      updateBrowserPagination();
    });
  }
  if (spellNext) {
    spellNext.addEventListener("click", () => {
      if (spellNext.classList.contains("is-disabled")) {
        return;
      }
      const maxPage = Math.ceil(spells.length / SPELLS_PER_PAGE) - 1;
      browserPage = Math.min(maxPage, browserPage + 1);
      renderBrowser();
      updateBrowserPagination();
    });
  }
  if (bookPrev) {
    bookPrev.addEventListener("click", () => {
      if (bookPrev.classList.contains("is-disabled")) {
        return;
      }
      bookPage = Math.max(0, bookPage - 1);
      updateBookTitle();
      renderWheel();
      updateBookPagination();
    });
  }
  if (bookNext) {
    bookNext.addEventListener("click", () => {
      if (bookNext.classList.contains("is-disabled")) {
        return;
      }
      bookPage = Math.min(SPELLBOOK_COUNT - 1, bookPage + 1);
      updateBookTitle();
      renderWheel();
      updateBookPagination();
    });
  }
  if (loadButton) {
    loadButton.addEventListener("click", openCharacterFile);
  }
  if (characterInput) {
    characterInput.addEventListener("change", (event) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      characterFileHandle = null;
      characterFileName = file.name;
      file.text().then(handleCharacterFile);
    });
  }
  if (saveButton) {
    saveButton.addEventListener("click", saveCharacter);
  }
  spellSlots.forEach((slot) => {
    slot.addEventListener("mouseenter", (event) => {
      const index = Number(slot.dataset.spellIndex);
      const spell = spells[index];
      if (!spell) {
        return;
      }
      showTooltip(spell, event);
    });
    slot.addEventListener("mousemove", onTooltipMove);
    slot.addEventListener("mouseleave", hideTooltip);
  });
  spellSlotContents.forEach((content) => {
    const slot = content.closest(".spell-slot");
    if (!slot) {
      return;
    }
    content.addEventListener("mouseenter", (event) => {
      const spellId = slot.dataset.spellId;
      const spell = spellMap.get(spellId);
      if (!spell) {
        return;
      }
      showTooltip(spell, event);
    });
    content.addEventListener("mousemove", onTooltipMove);
    content.addEventListener("mouseleave", hideTooltip);
  });
  spellSlotsRadial.forEach((slot) => {
    slot.addEventListener("contextmenu", (event) => {
      const slotIndex = Number(slot.dataset.slot);
      openContextMenu(event, slotIndex);
    });
  });
  if (contextMenu) {
    contextMenu.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) {
        return;
      }
      if (target.dataset.action === "clear" && contextSlotIndex !== null) {
        const absoluteIndex = getAbsoluteIndex(contextSlotIndex);
        selectedSpells[absoluteIndex] = "";
        renderWheel();
      }
      closeContextMenu();
    });
    window.addEventListener("click", (event) => {
      if (!contextMenu.classList.contains("hidden") && !contextMenu.contains(event.target)) {
        closeContextMenu();
      }
    });
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeContextMenu();
      }
    });
  }
}

async function loadSpells() {
  try {
    const response = await fetch(SPELLS_URL);
    spells = await response.json();
    spellMap = new Map(spells.map((spell) => [spell.persistence_id, spell]));
    updateSpellTitle();
    renderBrowser();
    updateBrowserPagination();
    updateBookTitle();
    renderWheel();
    updateBookPagination();
  } catch (error) {
    setStatus("Failed to load spell catalog.", false);
  }
}

setStatus("Load a character file to edit spellbooks.", false);
bindEvents();
bindDragAndDrop();
loadSpells();
