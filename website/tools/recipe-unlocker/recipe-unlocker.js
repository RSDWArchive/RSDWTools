const recipeGrid = document.querySelector(".item-grid--recipes");
const recipeSlots = recipeGrid
  ? Array.from(recipeGrid.querySelectorAll(".recipe-slot"))
  : [];
const recipeSearchInput = document.getElementById("recipe-search");
const recipeSearchClear = document.getElementById("recipe-search-clear");
const recipeTitle = document.getElementById("recipe-title");
const recipePrev = document.getElementById("recipe-prev");
const recipeNext = document.getElementById("recipe-next");
const recipeDots = document.getElementById("recipe-dots");
const recipeContextMenu = document.getElementById("recipe-context-menu");
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

const RECIPES_URL = "/tools/recipe-unlocker/data/recipes.json";
const ICONS_BASE = "/shared/icons/";
const CHECKED_ICON = "/shared/assets/checked.png";
const PAGE_SIZE = 64;

let allRecipes = [];
let filteredRecipes = [];
let currentPage = 0;
let unlockedIds = new Set();
let characterSource = null;
let characterFileName = null;
let characterFileHandle = null;
let contextRecipeIndex = null;

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

function updateTitle() {
  if (!recipeTitle) {
    return;
  }
  const count = filteredRecipes.length;
  recipeTitle.textContent = `All Recipes (${count})`;
}

function iconPath(iconName) {
  if (!iconName) {
    return "";
  }
  return `${ICONS_BASE}${iconName}`;
}

function clearSlot(slot) {
  slot.classList.remove("has-item");
  slot.removeAttribute("data-recipe-index");
  slot.innerHTML = "";
}

function renderSlot(slot, recipe, index) {
  clearSlot(slot);
  if (!recipe) {
    return;
  }
  slot.classList.add("has-item");
  slot.dataset.recipeIndex = String(index);

  const icon = document.createElement("img");
  icon.className = "item-icon";
  icon.src = iconPath(recipe.icon);
  icon.alt = "";
  slot.appendChild(icon);

  if (unlockedIds.has(recipe.persistence_id)) {
    const overlay = document.createElement("img");
    overlay.className = "recipe-unlocked";
    overlay.src = CHECKED_ICON;
    overlay.alt = "Unlocked";
    slot.appendChild(overlay);
  }
}

function renderGrid() {
  const start = currentPage * PAGE_SIZE;
  const pageItems = filteredRecipes.slice(start, start + PAGE_SIZE);
  recipeSlots.forEach((slot, idx) => {
    renderSlot(slot, pageItems[idx], start + idx);
  });
}

function updatePagination() {
  const pageCount = Math.max(1, Math.ceil(filteredRecipes.length / PAGE_SIZE));
  const isFirst = currentPage === 0;
  const isLast = currentPage >= pageCount - 1;

  if (recipePrev) {
    recipePrev.classList.toggle("is-disabled", isFirst);
    const img = recipePrev.querySelector("img");
    if (img) {
      img.src = isFirst ? img.dataset.disabledSrc : img.dataset.enabledSrc;
    }
  }
  if (recipeNext) {
    recipeNext.classList.toggle("is-disabled", isLast);
    const img = recipeNext.querySelector("img");
    if (img) {
      img.src = isLast ? img.dataset.disabledSrc : img.dataset.enabledSrc;
    }
  }

  if (!recipeDots) {
    return;
  }
  recipeDots.innerHTML = "";
  for (let i = 0; i < pageCount; i += 1) {
    const dot = document.createElement("img");
    dot.src =
      i === currentPage
        ? "/shared/game-ui/ItemBrowser/Current_Page_Dot.png"
        : "/shared/game-ui/ItemBrowser/Non_Selected_Page_Dot.png";
    dot.alt = i === currentPage ? "Current page" : "Page";
    dot.addEventListener("click", () => {
      currentPage = i;
      renderGrid();
      updatePagination();
    });
    recipeDots.appendChild(dot);
  }
}

function applyFilter(query) {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    filteredRecipes = [...allRecipes];
  } else {
    filteredRecipes = allRecipes.filter((recipe) => {
      const name = recipe.display_name || recipe.name || "";
      const rowName = recipe.row_name || "";
      return (
        name.toLowerCase().includes(needle) ||
        rowName.toLowerCase().includes(needle)
      );
    });
  }
  currentPage = 0;
  updateTitle();
  renderGrid();
  updatePagination();
}

function buildTooltip(recipe) {
  if (!tooltip || !tooltipName || !tooltipDesc || !tooltipMeta || !recipe) {
    return;
  }
  tooltipName.innerHTML = "";
  const nameIconWrap = document.createElement("div");
  nameIconWrap.className = "tooltip__icon tooltip__icon--power";
  const nameIcon = document.createElement("img");
  nameIcon.src = iconPath(recipe.icon);
  nameIcon.alt = "";
  nameIconWrap.appendChild(nameIcon);
  tooltipName.appendChild(nameIconWrap);
  const nameText = document.createElement("div");
  nameText.textContent = recipe.display_name || recipe.name || "Recipe";
  tooltipName.appendChild(nameText);

  tooltipDesc.textContent = "";
  tooltipMeta.innerHTML = "";

  const consumed = recipe.items_consumed || [];
  if (!consumed.length) {
    const empty = document.createElement("div");
    empty.textContent = "No ingredients listed.";
    tooltipMeta.appendChild(empty);
    return;
  }
  consumed.forEach((item) => {
    const line = document.createElement("div");
    line.className = "tooltip__row";
    const iconWrap = document.createElement("div");
    iconWrap.className = "tooltip__icon";
    const icon = document.createElement("img");
    icon.src = iconPath(item.icon);
    icon.alt = "";
    iconWrap.appendChild(icon);
    line.appendChild(iconWrap);
    const value = document.createElement("div");
    value.textContent = `${item.display_name || item.item_id} × ${item.count}`;
    line.appendChild(value);
    tooltipMeta.appendChild(line);
  });
}

function showTooltip(recipe, event) {
  if (!tooltip) {
    return;
  }
  buildTooltip(recipe);
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

function findRecipesUnlocked(data) {
  if (!data || typeof data !== "object") {
    return null;
  }
  if (Array.isArray(data)) {
    for (const item of data) {
      const found = findRecipesUnlocked(item);
      if (found) {
        return found;
      }
    }
    return null;
  }
  if (Object.prototype.hasOwnProperty.call(data, "RecipesUnlocked")) {
    return data.RecipesUnlocked;
  }
  for (const value of Object.values(data)) {
    const found = findRecipesUnlocked(value);
    if (found) {
      return found;
    }
  }
  return null;
}

function applyUnlocked(recipesUnlocked) {
  unlockedIds = new Set(Array.isArray(recipesUnlocked) ? recipesUnlocked : []);
  renderGrid();
  const unlockedCount = unlockedIds.size;
  setStatus(`Unlocked recipes: ${unlockedCount}`, true);
}

function setRecipesUnlocked(data, values) {
  if (!data || typeof data !== "object") {
    return false;
  }
  if (Array.isArray(data)) {
    for (const item of data) {
      if (setRecipesUnlocked(item, values)) {
        return true;
      }
    }
    return false;
  }
  if (Object.prototype.hasOwnProperty.call(data, "RecipesUnlocked")) {
    data.RecipesUnlocked = values;
    return true;
  }
  for (const value of Object.values(data)) {
    if (setRecipesUnlocked(value, values)) {
      return true;
    }
  }
  return false;
}

function buildExportData() {
  if (!characterSource) {
    return null;
  }
  const clone = JSON.parse(JSON.stringify(characterSource));
  const values = Array.from(unlockedIds).sort();
  if (!setRecipesUnlocked(clone, values)) {
    clone.RecipesUnlocked = values;
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
    const recipesUnlocked = findRecipesUnlocked(data) || [];
    applyUnlocked(recipesUnlocked);
  } catch (error) {
    setStatus("Failed to parse character JSON.", false);
  }
}

function openContextMenu(event, recipeIndex) {
  if (!recipeContextMenu) {
    return;
  }
  event.preventDefault();
  contextRecipeIndex = recipeIndex;
  recipeContextMenu.style.left = `${event.clientX}px`;
  recipeContextMenu.style.top = `${event.clientY}px`;
  recipeContextMenu.classList.remove("hidden");
}

function closeContextMenu() {
  if (!recipeContextMenu) {
    return;
  }
  recipeContextMenu.classList.add("hidden");
  contextRecipeIndex = null;
}

function toggleRecipeUnlock(shouldUnlock) {
  if (contextRecipeIndex === null) {
    return;
  }
  const recipe = filteredRecipes[contextRecipeIndex];
  if (!recipe) {
    return;
  }
  if (shouldUnlock) {
    unlockedIds.add(recipe.persistence_id);
  } else {
    unlockedIds.delete(recipe.persistence_id);
  }
  renderGrid();
  setStatus(`Unlocked recipes: ${unlockedIds.size}`, true);
}

function bindSlotEvents() {
  recipeSlots.forEach((slot) => {
    slot.addEventListener("mouseenter", (event) => {
      const index = Number(slot.dataset.recipeIndex);
      if (Number.isNaN(index)) {
        return;
      }
      const recipe = filteredRecipes[index];
      if (!recipe) {
        return;
      }
      showTooltip(recipe, event);
    });
    slot.addEventListener("mousemove", onTooltipMove);
    slot.addEventListener("mouseleave", hideTooltip);
    slot.addEventListener("contextmenu", (event) => {
      const index = Number(slot.dataset.recipeIndex);
      if (Number.isNaN(index)) {
        return;
      }
      const recipe = filteredRecipes[index];
      if (!recipe) {
        return;
      }
      openContextMenu(event, index);
    });
  });
}

function bindControls() {
  if (recipeSearchInput) {
    recipeSearchInput.addEventListener("input", () => {
      applyFilter(recipeSearchInput.value);
      if (recipeSearchClear) {
        recipeSearchClear.classList.toggle(
          "is-hidden",
          recipeSearchInput.value.length === 0
        );
      }
    });
  }
  if (recipeSearchClear) {
    recipeSearchClear.addEventListener("click", () => {
      if (!recipeSearchInput) {
        return;
      }
      recipeSearchInput.value = "";
      recipeSearchClear.classList.add("is-hidden");
      applyFilter("");
    });
  }
  if (recipePrev) {
    recipePrev.addEventListener("click", () => {
      if (recipePrev.classList.contains("is-disabled")) {
        return;
      }
      currentPage = Math.max(0, currentPage - 1);
      renderGrid();
      updatePagination();
    });
  }
  if (recipeNext) {
    recipeNext.addEventListener("click", () => {
      if (recipeNext.classList.contains("is-disabled")) {
        return;
      }
      const pageCount = Math.ceil(filteredRecipes.length / PAGE_SIZE);
      currentPage = Math.min(pageCount - 1, currentPage + 1);
      renderGrid();
      updatePagination();
    });
  }
  if (loadButton && characterInput) {
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
  if (recipeContextMenu) {
    recipeContextMenu.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) {
        return;
      }
      const action = target.dataset.action;
      if (action === "unlock") {
        toggleRecipeUnlock(true);
      } else if (action === "remove") {
        toggleRecipeUnlock(false);
      }
      closeContextMenu();
    });
    window.addEventListener("click", (event) => {
      if (
        !recipeContextMenu.classList.contains("hidden") &&
        !recipeContextMenu.contains(event.target)
      ) {
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

async function loadRecipes() {
  try {
    const response = await fetch(RECIPES_URL);
    allRecipes = await response.json();
    filteredRecipes = [...allRecipes];
    updateTitle();
    renderGrid();
    updatePagination();
  } catch (error) {
    setStatus("Failed to load recipe catalog.", false);
    console.error(error);
  }
}

setStatus("Load a character file to highlight unlocked recipes.", false);
bindSlotEvents();
bindControls();
loadRecipes();
