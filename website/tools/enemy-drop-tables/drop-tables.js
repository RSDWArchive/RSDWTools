const DATA_PATHS = {
  lootData: "/data/loot_data.json",
  items: "/data/chest_item_catalog.json",
};

const searchInput = document.getElementById("enemy-search");
const searchClear = document.getElementById("enemy-search-clear");
const suggestions = document.getElementById("enemy-suggestions");
const enemyTitle = document.getElementById("drop-enemy-name");
const enemySubtitle = document.getElementById("drop-enemy-subtitle");
const resultsHeader = document.querySelector(".drop-results__header");
const emptyState = document.getElementById("drop-empty");
const table = document.getElementById("drop-table");
const tableBody = document.getElementById("drop-table-body");

const state = {
  enemyLoot: {},
  enemyDisplayList: [],
  enemyDisplayToInternal: new Map(),
  itemCatalog: new Map(),
  activeEnemyDisplay: "",
  suggestionItems: [],
  activeSuggestionIndex: -1,
};

function normalizeText(value) {
  return String(value ?? "").trim().toLowerCase();
}

function normalizeAssetPath(path) {
  if (!path) {
    return path;
  }
  return encodeURI(String(path));
}

function formatPercent(value) {
  const num = Number(value);
  if (Number.isNaN(num)) {
    return "";
  }
  const normalized = num
    .toFixed(2)
    .replace(/\.00$/, "")
    .replace(/(\.\d)0$/, "$1");
  return `${normalized}%`;
}

function formatQuantity(min, max) {
  if (typeof min === "undefined" || typeof max === "undefined") {
    return "";
  }
  if (min === max) {
    return String(min);
  }
  return `${min}-${max}`;
}

function prettifyName(value) {
  const source = String(value ?? "").trim();
  if (!source) {
    return "";
  }
  const spaced = source
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.replace(/\s+/g, " ").trim();
}

function buildWikiUrl(name) {
  if (!name) {
    return null;
  }
  const slug = String(name).trim().replace(/\s+/g, "_");
  return `https://dragonwilds.runescape.wiki/w/${encodeURI(slug)}`;
}

function clearSuggestions() {
  suggestions.innerHTML = "";
  suggestions.classList.remove("is-visible");
  state.suggestionItems = [];
  state.activeSuggestionIndex = -1;
}

function showSuggestions(items) {
  suggestions.innerHTML = "";
  state.suggestionItems = items;
  state.activeSuggestionIndex = -1;
  if (!items.length) {
    clearSuggestions();
    return;
  }
  items.forEach((name) => {
    const li = document.createElement("li");
    li.className = "drop-search__suggestion";
    li.textContent = name;
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", "false");
    li.tabIndex = -1;
    li.addEventListener("mousedown", (event) => {
      event.preventDefault();
      selectEnemy(name);
    });
    suggestions.appendChild(li);
  });
  suggestions.classList.add("is-visible");
}

function updateSuggestionHighlight() {
  const nodes = suggestions.querySelectorAll(".drop-search__suggestion");
  nodes.forEach((node, index) => {
    const isActive = index === state.activeSuggestionIndex;
    node.classList.toggle("is-active", isActive);
    node.setAttribute("aria-selected", isActive ? "true" : "false");
    if (isActive) {
      node.scrollIntoView({ block: "nearest" });
    }
  });
}

function showEmptyState(message) {
  emptyState.textContent = message;
  emptyState.classList.remove("is-hidden");
  emptyState.hidden = false;
  table.classList.add("is-hidden");
  table.hidden = true;
}

function hideEmptyState() {
  emptyState.classList.add("is-hidden");
  emptyState.hidden = true;
}

function renderTable(alwaysRows, bonusRows) {
  tableBody.innerHTML = "";

  const appendSection = (label, rows) => {
    if (!rows.length) {
      return;
    }
    const sectionRow = document.createElement("tr");
    sectionRow.className = "drop-table__section";
    const sectionCell = document.createElement("th");
    sectionCell.colSpan = 3;
    sectionCell.textContent = label;
    sectionRow.appendChild(sectionCell);
    tableBody.appendChild(sectionRow);

    rows.forEach((row) => {
      const tr = document.createElement("tr");

      const itemCell = document.createElement("td");
      const itemWrap = document.createElement("div");
      itemWrap.className = "drop-item";
      const icon = document.createElement("img");
      icon.className = "drop-item__icon";
      icon.alt = row.displayName;
      icon.loading = "lazy";
      if (row.iconPath) {
        icon.src = row.iconPath;
      } else {
        icon.classList.add("is-missing");
        icon.src = "/shared/game-ui/Inventory/Item_BG.png";
      }
      const nameLink = document.createElement("a");
      nameLink.className = "drop-item__name";
      nameLink.textContent = row.displayName;
      nameLink.href = row.wikiUrl ?? "#";
      nameLink.target = "_blank";
      nameLink.rel = "noopener";
      itemWrap.appendChild(icon);
      itemWrap.appendChild(nameLink);
      itemCell.appendChild(itemWrap);

      const quantityCell = document.createElement("td");
      quantityCell.textContent = row.quantity;

      const rarityCell = document.createElement("td");
      rarityCell.textContent = row.rarity;

      tr.appendChild(itemCell);
      tr.appendChild(quantityCell);
      tr.appendChild(rarityCell);
      tableBody.appendChild(tr);
    });
  };

  appendSection("Always", alwaysRows);
  appendSection("Bonus", bonusRows);

  hideEmptyState();
  table.classList.remove("is-hidden");
  table.hidden = false;
}

function buildRows(resources) {
  return resources.map((resource) => {
    const itemId = resource?.itemId || "";
    const itemMeta = itemId ? state.itemCatalog.get(itemId) : null;
    const displayName =
      itemMeta?.display_name || prettifyName(itemId) || "Unknown Item";
    const chanceValue = Number(resource?.dropChance ?? 0);
    return {
      displayName,
      iconPath: itemMeta?.icon
        ? normalizeAssetPath(`/shared/icons/${itemMeta.icon}`)
        : "",
      wikiUrl: buildWikiUrl(displayName),
      quantity: formatQuantity(
        resource?.minimumDropAmount,
        resource?.maximumDropAmount
      ),
      rarity: formatPercent(resource?.dropChance),
      chanceValue,
    };
  });
}

function renderEnemyLoot(displayName) {
  const internalKey =
    state.enemyDisplayToInternal.get(normalizeText(displayName)) ?? null;
  const drops = internalKey ? state.enemyLoot[internalKey] : null;

  state.activeEnemyDisplay = displayName;
  resultsHeader.classList.remove("is-hidden");
  resultsHeader.hidden = false;
  enemyTitle.textContent = displayName || "Select an NPC";
  enemySubtitle.textContent = "";
  if (internalKey && displayName) {
    const enemyLink = document.createElement("a");
    enemyLink.href = buildWikiUrl(displayName);
    enemyLink.target = "_blank";
    enemyLink.rel = "noopener";
    enemyLink.textContent = "View on Wiki";
    enemySubtitle.appendChild(enemyLink);
  } else if (displayName) {
    enemySubtitle.textContent = "No match found.";
  }

  const resources = drops ?? [];
  if (!resources.length) {
    table.classList.add("is-hidden");
    table.hidden = true;
    hideEmptyState();
    return;
  }
  const rows = buildRows(resources);
  const alwaysRows = rows.filter((rowItem) => rowItem.chanceValue === 100);
  const bonusRows = rows
    .filter((rowItem) => rowItem.chanceValue !== 100)
    .sort((a, b) => b.chanceValue - a.chanceValue);
  renderTable(alwaysRows, bonusRows);
}

function selectEnemy(displayName) {
  searchInput.value = displayName;
  searchClear.classList.remove("is-hidden");
  clearSuggestions();
  renderEnemyLoot(displayName);
}

function handleInput() {
  const value = searchInput.value;
  const query = normalizeText(value);
  if (!query) {
    searchClear.classList.add("is-hidden");
    clearSuggestions();
    resultsHeader.classList.add("is-hidden");
    resultsHeader.hidden = true;
    enemyTitle.textContent = "Select an NPC";
    enemySubtitle.textContent = "";
    tableBody.innerHTML = "";
    table.classList.add("is-hidden");
    table.hidden = true;
    state.activeEnemyDisplay = "";
    showEmptyState("Type in an NPC name to see its loot table.");
    return;
  }
  searchClear.classList.remove("is-hidden");
  hideEmptyState();

  const matches = state.enemyDisplayList.filter((name) =>
    normalizeText(name).includes(query)
  );
  showSuggestions(matches.slice(0, 8));
}

function handleSubmit() {
  const value = searchInput.value;
  const key = normalizeText(value);
  if (state.activeSuggestionIndex >= 0) {
    const suggestion = state.suggestionItems[state.activeSuggestionIndex];
    if (suggestion) {
      selectEnemy(suggestion);
      return;
    }
  }
  const match = state.enemyDisplayToInternal.get(key);
  if (match) {
    selectEnemy(value.trim());
  } else {
    renderEnemyLoot(value.trim());
  }
}

async function loadData() {
  const [lootData, items] = await Promise.all([
    fetch(DATA_PATHS.lootData).then((res) => res.json()),
    fetch(DATA_PATHS.items).then((res) => res.json()),
  ]);

  const enemyRows = lootData?.enemies ?? {};
  const enemyLoot = {};
  const displayList = [];
  const displayToInternal = new Map();
  Object.entries(enemyRows).forEach(([internal, entry]) => {
    enemyLoot[internal] = entry?.drops ?? [];
    const displayName = prettifyName(internal);
    if (!displayName) {
      return;
    }
    displayList.push(displayName);
    displayToInternal.set(normalizeText(displayName), internal);
  });
  state.enemyLoot = enemyLoot;
  displayList.sort((a, b) => a.localeCompare(b));
  state.enemyDisplayList = displayList;
  state.enemyDisplayToInternal = displayToInternal;

  const itemCatalog = new Map();
  (items ?? []).forEach((item) => {
    if (!item?.item_id || itemCatalog.has(item.item_id)) {
      return;
    }
    itemCatalog.set(item.item_id, item);
  });
  state.itemCatalog = itemCatalog;
}

function init() {
  loadData()
    .then(() => {
      handleInput();
    })
    .catch(() => {
      showEmptyState("Failed to load drop table data.");
    });

  searchInput.addEventListener("input", handleInput);
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSubmit();
      clearSuggestions();
    } else if (event.key === "ArrowDown") {
      if (!state.suggestionItems.length) {
        return;
      }
      event.preventDefault();
      state.activeSuggestionIndex =
        (state.activeSuggestionIndex + 1) % state.suggestionItems.length;
      updateSuggestionHighlight();
    } else if (event.key === "ArrowUp") {
      if (!state.suggestionItems.length) {
        return;
      }
      event.preventDefault();
      state.activeSuggestionIndex =
        (state.activeSuggestionIndex - 1 + state.suggestionItems.length) %
        state.suggestionItems.length;
      updateSuggestionHighlight();
    } else if (event.key === "Escape") {
      clearSuggestions();
    }
  });

  searchInput.addEventListener("blur", () => {
    setTimeout(() => clearSuggestions(), 100);
  });

  searchClear.addEventListener("click", () => {
    searchInput.value = "";
    searchInput.focus();
    handleInput();
  });
}

init();
