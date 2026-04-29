const DATA_PATHS = {
  lootData: "/data/loot_data.json",
  items: "/data/chest_item_catalog.json",
};

const chestSelect = document.getElementById("chest-select");
const chestTitle = document.getElementById("drop-chest-name");
const chestSubtitle = document.getElementById("drop-chest-subtitle");
const resultsHeader = document.querySelector(".drop-results__header");
const emptyState = document.getElementById("drop-empty");
const table = document.getElementById("drop-table");
const tableBody = document.getElementById("drop-table-body");

const state = {
  chests: {},
  itemSets: {},
  itemCatalog: new Map(),
};

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

function formatRespawnTime(time) {
  if (!time) {
    return "";
  }
  const parts = [
    { key: "Days", label: "d" },
    { key: "Hours", label: "h" },
    { key: "Minutes", label: "m" },
    { key: "Seconds", label: "s" },
  ];
  const values = parts
    .map(({ key, label }) => {
      const value = Number(time[key] ?? 0);
      return value ? `${value}${label}` : "";
    })
    .filter(Boolean);
  return values.length ? values.join(" ") : "0s";
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

function renderTable(sections) {
  tableBody.innerHTML = "";

  sections.forEach((section) => {
    if (!section.rows.length) {
      return;
    }
    const sectionRow = document.createElement("tr");
    sectionRow.className = "drop-table__section";
    const sectionCell = document.createElement("th");
    sectionCell.colSpan = 4;
    sectionCell.textContent = section.label;
    sectionRow.appendChild(sectionCell);
    tableBody.appendChild(sectionRow);

    section.rows.forEach((row) => {
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

      const chanceCell = document.createElement("td");
      chanceCell.textContent = row.chance;

      const sourceCell = document.createElement("td");
      sourceCell.className = "drop-table__source";
      sourceCell.textContent = row.source;

      tr.appendChild(itemCell);
      tr.appendChild(quantityCell);
      tr.appendChild(chanceCell);
      tr.appendChild(sourceCell);
      tableBody.appendChild(tr);
    });
  });

  hideEmptyState();
  table.classList.remove("is-hidden");
  table.hidden = false;
}

function buildRowsFromItems(items, label, setName, setChance) {
  return items.map((resource) => {
    const itemId = resource?.itemId || "";
    const catalogItem = itemId ? state.itemCatalog.get(itemId) : null;
    const displayName =
      catalogItem?.display_name ||
      prettifyName(itemId) ||
      itemId ||
      "Unknown Item";
    const itemChance = Number(resource?.dropChance ?? 0);
    const chanceParts = [];
    if (typeof setChance === "number") {
      chanceParts.push(`Set ${formatPercent(setChance)}`);
    } else if (label.toLowerCase().includes("guaranteed")) {
      chanceParts.push("Guaranteed");
    }
    if (!Number.isNaN(itemChance) && itemChance) {
      chanceParts.push(`Item ${formatPercent(itemChance)}`);
    }
    const combinedChance =
      (typeof setChance === "number" ? setChance : 100) *
      (itemChance || 100) /
      100;
    return {
      displayName,
      iconPath: catalogItem?.icon
        ? normalizeAssetPath(`/shared/icons/${catalogItem.icon}`)
        : "",
      wikiUrl: buildWikiUrl(displayName),
      quantity: formatQuantity(
        resource?.minimumDropAmount,
        resource?.maximumDropAmount
      ),
      chance: chanceParts.join(" \u2022 ") || "",
      source: `${label}: ${setName}`,
      chanceValue: combinedChance,
    };
  });
}

function renderChest(key) {
  const chest = state.chests[key];
  if (!key || !chest) {
    resultsHeader.classList.add("is-hidden");
    resultsHeader.hidden = true;
    showEmptyState("Select a chest to see loot drops.");
    return;
  }

  resultsHeader.classList.remove("is-hidden");
  resultsHeader.hidden = false;
  chestTitle.textContent = key;

  chestSubtitle.textContent = "";
  const respawnText = formatRespawnTime(chest?.respawn?.inGameRespawnTime);
  if (respawnText) {
    chestSubtitle.textContent = `Respawn: ${respawnText}`;
  }

  const sections = [];
  const guaranteedRows = [];
  const bonusRows = [];
  const guaranteedSetRows = chest.guaranteedSetRows ?? [];
  const additionalSetRows = chest.additionalSetRows ?? [];

  guaranteedSetRows.forEach((setName) => {
    const setItems = state.itemSets[setName] ?? [];
    if (!setItems.length) {
      return;
    }
    guaranteedRows.push(
      ...buildRowsFromItems(
        setItems,
        "Guaranteed Set",
        setName,
        null
      )
    );
  });

  additionalSetRows.forEach((entry) => {
    const setName = entry?.setRow ?? "";
    const setItems = state.itemSets[setName] ?? [];
    if (!setItems.length) {
      return;
    }
    bonusRows.push(
      ...buildRowsFromItems(
        setItems,
        "Bonus Set",
        setName,
        entry?.setRollChance
      )
    );
  });

  if (guaranteedRows.length) {
    sections.push({ label: "Guaranteed Sets", rows: guaranteedRows });
  }

  if (bonusRows.length) {
    sections.push({
      label: `Bonus Sets (0-${additionalSetRows.length} rolls)`,
      rows: bonusRows.sort((a, b) => b.chanceValue - a.chanceValue),
    });
  }

  if (!sections.length) {
    showEmptyState("No loot data found for this chest.");
    return;
  }

  renderTable(sections);
}

async function loadData() {
  const [lootData, items] = await Promise.all([
    fetch(DATA_PATHS.lootData).then((res) => res.json()),
    fetch(DATA_PATHS.items).then((res) => res.json()),
  ]);
  state.chests = lootData?.chests ?? {};
  state.itemSets = lootData?.itemSets ?? {};

  const itemCatalog = new Map();
  (items ?? []).forEach((item) => {
    if (!item?.item_id || itemCatalog.has(item.item_id)) {
      return;
    }
    itemCatalog.set(item.item_id, item);
  });
  state.itemCatalog = itemCatalog;

  const keys = Object.keys(state.chests).sort((a, b) =>
    a.localeCompare(b)
  );
  keys.forEach((key) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = key;
    chestSelect.appendChild(option);
  });
}

function bindEvents() {
  chestSelect.addEventListener("change", (event) => {
    renderChest(event.target.value);
  });
}

bindEvents();
loadData().catch((error) => {
  console.error("[Chest Tables] Failed to load data", error);
  showEmptyState("Failed to load chest data.");
});
