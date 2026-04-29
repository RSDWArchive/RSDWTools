const TAB_CONFIG = {
  bag: {
    label: "Bag Items",
    selected: "/shared/game-ui/Inventory/BagTab_Selected.png",
    normal: "/shared/game-ui/Inventory/BagTab_Normal.png",
  },
  rune: {
    label: "Rune Items",
    selected: "/shared/game-ui/Inventory/RuneTab_Selected.png",
    normal: "/shared/game-ui/Inventory/RuneTab_Normal.png",
  },
  ammo: {
    label: "Ammo Items",
    selected: "/shared/game-ui/Inventory/AmmoTab_Selected.png",
    normal: "/shared/game-ui/Inventory/AmmoTab_Normal.png",
  },
  quest: {
    label: "Quest Items",
    selected: "/shared/game-ui/Inventory/QuestTab_Selected.png",
    normal: "/shared/game-ui/Inventory/QuestTab_Normal.png",
  },
};

const tabButtons = document.querySelectorAll(".tab-button");
const itembrowserTitle = document.getElementById("itembrowser-title");
const browserSlots = document.querySelectorAll(".item-grid--browser .item-slot");
const paginationDots = document.querySelector(".pagination-dots");
const statusText = document.getElementById("status-text");
const statusBar = document.querySelector(".status-bar");
const statusIcon = document.querySelector(".status-bar__icon");
const tooltip = document.getElementById("tooltip");
const tooltipName = document.getElementById("tooltip-name");
const tooltipDesc = document.getElementById("tooltip-desc");
const tooltipMeta = document.getElementById("tooltip-meta");
const characterInput = document.getElementById("character-file");
const saveButton = document.getElementById("save-button");
const browserPrev = document.getElementById("browser-prev");
const browserNext = document.getElementById("browser-next");
const itemSearch = document.getElementById("item-search");
const itemSearchClear = document.getElementById("item-search-clear");
const contextMenu = document.getElementById("context-menu");
const bagCategories = document.getElementById("bag-categories");
const countModal = document.getElementById("count-modal");
const countInput = document.getElementById("count-input");
const countHint = document.getElementById("count-hint");
const countCancel = document.getElementById("count-cancel");
const countApply = document.getElementById("count-apply");
const alertModal = document.getElementById("alert-modal");
const alertMessage = document.getElementById("alert-message");
const alertOk = document.getElementById("alert-ok");
const loadButton = document.getElementById("load-button");
const loadIcon = document.getElementById("load-icon");

const actionSlots = document.querySelectorAll('[data-slot-type="action"]');
const tabbedSlots = document.querySelectorAll('[data-slot-type="tabbed"]');
const personalSlots = document.querySelectorAll('[data-slot-type="personal"]');
const loadoutSlots = document.querySelectorAll('[data-slot-type="loadout"]');

const state = {
  activeTab: "bag",
  pageIndex: 0,
  catalog: null,
  catalogIndex: new Map(),
  inventory: {},
  personalInventory: {},
  loadout: {},
  characterSource: null,
  bagCategory: null,
  contextSlot: null,
  dragSourceSlot: null,
  dragDropped: false,
  dragPayload: null,
  modalSlot: null,
  contextSource: null,
  fileHandle: null,
  fileName: null,
  searchQuery: "",
};

const LOAD_ICON = "/shared/game-ui/Landing/Load_Character.png";
const LOADED_ICON = "/shared/game-ui/Landing/Character_Loaded.png";
const STATUS_ICON_UNLOADED = "/shared/game-ui/Status/status_unloaded_icon.png";
const STATUS_ICON_LOADED = "/shared/game-ui/Status/status_loaded_icon.png";

const PAGE_SIZE = 32;
const DOTS = {
  current: "/shared/game-ui/ItemBrowser/Current_Page_Dot.png",
  normal: "/shared/game-ui/ItemBrowser/Non_Selected_Page_Dot.png",
};
const TAB_OFFSETS = {
  bag: 8,
  rune: 32,
  ammo: 56,
  quest: 80,
};

const SLOT_LIMITS = {
  inventory: 103,
  personal: 19,
  loadout: 4,
};

const LOADOUT_SLOT_KEYS = ["Head", "Body", "Legs", "Cape", "Jewellery"];

const BAG_CATEGORY_CONFIG = [
  {
    key: "Armour",
    normal: "/shared/game-ui/ItemBrowser/BagTabCategories/Armour_Normal.png",
    selected: "/shared/game-ui/ItemBrowser/BagTabCategories/Armour_Selected.png",
  },
  {
    key: "Consumables",
    normal: "/shared/game-ui/ItemBrowser/BagTabCategories/Consumables_Normal.png",
    selected: "/shared/game-ui/ItemBrowser/BagTabCategories/Consumables_Selected.png",
  },
  {
    key: "Materials",
    normal: "/shared/game-ui/ItemBrowser/BagTabCategories/Materials_Normal.png",
    selected: "/shared/game-ui/ItemBrowser/BagTabCategories/Materials_Selected.png",
  },
  {
    key: "Tools",
    normal: "/shared/game-ui/ItemBrowser/BagTabCategories/Tools_Normal.png",
    selected: "/shared/game-ui/ItemBrowser/BagTabCategories/Tools_Selected.png",
  },
  {
    key: "Weapons",
    normal: "/shared/game-ui/ItemBrowser/BagTabCategories/Weapons_Normal.png",
    selected: "/shared/game-ui/ItemBrowser/BagTabCategories/Weapons_Selected.png",
  },
  {
    key: "Plans",
    normal: "/shared/game-ui/ItemBrowser/BagTabCategories/Plans_Vestiges_Normal.png",
    selected: "/shared/game-ui/ItemBrowser/BagTabCategories/Plans_Vestiges_Selected.png",
  },
];

const VITAL_SHIELD_CATEGORIES = new Set(["Armour", "Weapons", "Tools"]);

function normalizeAssetPath(path) {
  if (!path) {
    return path;
  }
  return encodeURI(String(path));
}

function normalizeCatalogPaths(catalog) {
  Object.values(catalog?.tabs ?? {}).forEach((tab) => {
    (tab.items ?? []).forEach((item) => {
      if (item.iconPath) {
        item.iconPath = normalizeAssetPath(item.iconPath);
      }
      if (item.sourcePath) {
        item.sourcePath = normalizeAssetPath(item.sourcePath);
      }
    });
  });
  return catalog;
}

function clearSlot(slot) {
  const overlay = slot.querySelector(".slot-overlay");
  slot.innerHTML = "";
  if (overlay) {
    slot.appendChild(overlay);
  }
  slot.classList.remove("has-item");
  slot.removeAttribute("title");
  slot.removeAttribute("data-item-data");
  slot.removeAttribute("data-item-name");
  slot.removeAttribute("data-description");
  slot.removeAttribute("data-weight");
  slot.removeAttribute("data-base-durability");
  slot.removeAttribute("data-power-level");
  slot.removeAttribute("data-max-stack");
  slot.removeAttribute("data-icon-path");
  slot.removeAttribute("data-source");
  slot.draggable = false;
  slot.ondragstart = null;
}

function renderBrowserSlots(items) {
  browserSlots.forEach((slot, index) => {
    clearSlot(slot);
    const item = items[index];
    if (!item) {
      return;
    }

    const icon = document.createElement("img");
    icon.className = "item-icon";
    icon.src = item.iconPath;
    icon.alt = item.name;
    slot.dataset.itemData = item.itemData ?? "";
    slot.dataset.itemName = item.name ?? "";
    slot.dataset.maxStack = String(item.maxStack ?? 1);
    slot.dataset.iconPath = item.iconPath ?? "";
    slot.dataset.source = "catalog";
    if (item.description) {
      slot.dataset.description = item.description;
    }
    if (typeof item.weight !== "undefined") {
      slot.dataset.weight = String(item.weight);
    }
    if (typeof item.powerLevel !== "undefined") {
      slot.dataset.powerLevel = String(item.powerLevel);
    }
    if (typeof item.baseDurability !== "undefined") {
      slot.dataset.baseDurability = String(item.baseDurability);
    }
    slot.draggable = true;
    slot.ondragstart = onDragStartFromCatalog;
    slot.appendChild(icon);
    slot.addEventListener("dblclick", onBrowserDoubleClick);
    slot.addEventListener("contextmenu", onBrowserContextMenu);
    slot.addEventListener("mouseenter", onBrowserMouseEnter);
    slot.addEventListener("mousemove", onTooltipMove);
    slot.addEventListener("mouseleave", hideTooltip);
  });
}

function renderPagination(totalItems) {
  if (!paginationDots) {
    return;
  }

  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
  paginationDots.innerHTML = "";

  for (let i = 0; i < totalPages; i += 1) {
    const dot = document.createElement("img");
    dot.src = i === state.pageIndex ? DOTS.current : DOTS.normal;
    dot.alt = i === state.pageIndex ? "Current page" : "Page";
    dot.addEventListener("click", () => {
      state.pageIndex = i;
      renderItemBrowser();
    });
    paginationDots.appendChild(dot);
  }
}

function updateBrowserArrows(totalItems) {
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
  if (browserPrev) {
    const disabled = state.pageIndex <= 0;
    browserPrev.classList.toggle("is-disabled", disabled);
    const img = browserPrev.querySelector("img");
    if (img) {
      img.src = disabled
        ? img.dataset.disabledSrc ?? img.src
        : img.dataset.enabledSrc ?? img.src;
    }
  }
  if (browserNext) {
    const disabled = state.pageIndex >= totalPages - 1;
    browserNext.classList.toggle("is-disabled", disabled);
    const img = browserNext.querySelector("img");
    if (img) {
      img.src = disabled
        ? img.dataset.disabledSrc ?? img.src
        : img.dataset.enabledSrc ?? img.src;
    }
  }
}

function renderItemBrowser() {
  if (!state.catalog) {
    return;
  }

  const tabData = state.catalog.tabs[state.activeTab];
  if (!tabData) {
    return;
  }

  let items = tabData.items ?? [];
  if (state.activeTab === "bag" && state.bagCategory) {
    items = items.filter((item) => {
      const category = item.category ?? "";
      const root = category.split("/")[0];
      if (state.bagCategory === "Plans") {
        return root === "Plans" || root === "Vestiges";
      }
      return root === state.bagCategory;
    });
  }
  if (state.searchQuery) {
    const query = state.searchQuery.toLowerCase();
    items = items.filter((item) => {
      const name = (item.name ?? "").toLowerCase();
      const category = (item.category ?? "").toLowerCase();
      return name.includes(query) || category.includes(query);
    });
  }
  const start = state.pageIndex * PAGE_SIZE;
  const pageItems = items.slice(start, start + PAGE_SIZE);
  renderBrowserSlots(pageItems);
  renderPagination(items.length);
  updateBrowserArrows(items.length);
  itembrowserTitle.textContent = tabData.label ?? TAB_CONFIG[state.activeTab].label;
}

function renderBagCategories() {
  if (!bagCategories) {
    return;
  }
  const isVisible = state.activeTab === "bag";
  bagCategories.style.display = isVisible ? "flex" : "none";
  if (!isVisible) {
    return;
  }

  bagCategories.innerHTML = "";
  BAG_CATEGORY_CONFIG.forEach((category) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "bag-category";
    button.dataset.category = category.key;
    const image = document.createElement("img");
    image.src =
      state.bagCategory === category.key ? category.selected : category.normal;
    image.alt = category.key;
    button.appendChild(image);
    button.addEventListener("click", () => {
      const next =
        state.bagCategory === category.key ? null : category.key;
      state.bagCategory = next;
      state.pageIndex = 0;
      renderBagCategories();
      renderItemBrowser();
    });
    bagCategories.appendChild(button);
  });
}

function setSlotContents(slot, item) {
  clearSlot(slot);
  if (!item) {
    slot.removeAttribute("data-item-data");
    return;
  }

  const meta = state.catalogIndex.get(item.ItemData);
  if (!meta || !meta.iconPath) {
    slot.dataset.itemData = item.ItemData;
    return;
  }

  const icon = document.createElement("img");
  icon.className = "item-icon";
  icon.src = meta.iconPath;
  icon.alt = meta.name ?? "Item";
  slot.appendChild(icon);
  slot.classList.add("has-item");
  slot.dataset.itemData = item.ItemData;
  slot.dataset.iconPath = meta.iconPath;
  slot.draggable = true;

  if (item.Count && item.Count > 1) {
    const count = document.createElement("div");
    count.className = "item-count";
    count.textContent = String(item.Count);
    slot.appendChild(count);
  }
}

function renderInventory() {
  actionSlots.forEach((slot) => {
    const index = Number(slot.dataset.slotIndex);
    const item = state.inventory[index];
    setSlotContents(slot, item);
  });

  tabbedSlots.forEach((slot) => {
    const tabIndex = Number(slot.dataset.tabIndex);
    const slotIndex = TAB_OFFSETS[state.activeTab] + tabIndex;
    const item = state.inventory[slotIndex];
    setSlotContents(slot, item);
  });

  personalSlots.forEach((slot) => {
    const index = Number(slot.dataset.slotIndex);
    const item = state.personalInventory[index];
    setSlotContents(slot, item);
  });

  loadoutSlots.forEach((slot) => {
    const index = Number(slot.dataset.loadoutIndex);
    const item = state.loadout[index];
    setSlotContents(slot, item);
  });
}

function buildCatalogIndex(catalog) {
  const index = new Map();
  Object.values(catalog.tabs ?? {}).forEach((tab) => {
    (tab.items ?? []).forEach((item) => {
      if (item.itemData) {
        index.set(item.itemData, item);
      }
    });
  });
  return index;
}

function setStatus(message) {
  if (statusText) {
    statusText.textContent = message;
  }
}

function setLoadUiState(isLoaded) {
  if (loadIcon) {
    loadIcon.src = isLoaded ? LOADED_ICON : LOAD_ICON;
  }
  if (saveButton) {
    saveButton.classList.toggle("hidden", !isLoaded);
  }
  if (statusBar) {
    statusBar.classList.toggle("status-bar--loaded", isLoaded);
    statusBar.classList.toggle("status-bar--unloaded", !isLoaded);
  }
  if (statusIcon) {
    statusIcon.src = isLoaded ? STATUS_ICON_LOADED : STATUS_ICON_UNLOADED;
  }
}

function shouldIncludeVitalShield(itemData) {
  const meta = state.catalogIndex.get(itemData);
  if (!meta) {
    return false;
  }
  if (typeof meta.vitalShield !== "undefined") {
    return true;
  }
  const category = meta.category ?? "";
  const root = category.split("/")[0];
  return VITAL_SHIELD_CATEGORIES.has(root);
}

function generateGuid() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  bytes.forEach((value) => {
    binary += String.fromCharCode(value);
  });
  const base64 = btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return base64;
}

function getLoadoutSlotKey(slot) {
  const index = Number(slot.dataset.loadoutIndex);
  return LOADOUT_SLOT_KEYS[index];
}

function getItemEquipment(itemData) {
  const meta = state.catalogIndex.get(itemData);
  return meta?.equipment ?? null;
}

function canPlaceItem(slot, payload) {
  const slotType = slot.dataset.slotType;
  if (payload?.source === "inventory") {
    if (slotType === "loadout") {
      const slotKey = getLoadoutSlotKey(slot);
      const itemData = payload?.itemData;
      if (!slotKey || !itemData) {
        return false;
      }
      return getItemEquipment(itemData) === slotKey;
    }
    return true;
  }
  if (slotType === "loadout") {
    const slotKey = getLoadoutSlotKey(slot);
    const itemData = payload?.itemData;
    if (!slotKey || !itemData) {
      return false;
    }
    return getItemEquipment(itemData) === slotKey;
  }
  if (slotType === "tabbed") {
    return true;
  }
  return state.activeTab === "bag";
}

function getInventorySlotIndex(slot) {
  const slotType = slot.dataset.slotType;
  if (slotType === "action") {
    return Number(slot.dataset.slotIndex);
  }
  if (slotType === "personal") {
    return Number(slot.dataset.slotIndex);
  }
  if (slotType === "tabbed") {
    return TAB_OFFSETS[state.activeTab] + Number(slot.dataset.tabIndex);
  }
  return null;
}

function updateSlotItem(slot, item) {
  const slotType = slot.dataset.slotType;
  if (slotType === "personal") {
    const index = Number(slot.dataset.slotIndex);
    if (item) {
      state.personalInventory[index] = item;
    } else {
      delete state.personalInventory[index];
    }
  } else if (slotType === "loadout") {
    const index = Number(slot.dataset.loadoutIndex);
    if (item) {
      state.loadout[index] = item;
    } else {
      delete state.loadout[index];
    }
  } else {
    const index = getInventorySlotIndex(slot);
    if (index === null) {
      return;
    }
    if (item) {
      state.inventory[index] = item;
    } else {
      delete state.inventory[index];
    }
  }
  renderInventory();
}

function onDragStartFromCatalog(event) {
  const slot = event.currentTarget;
  const payload = {
    source: "catalog",
    itemData: slot.dataset.itemData,
    itemName: slot.dataset.itemName,
    iconPath: slot.dataset.iconPath,
    maxStack: Number(slot.dataset.maxStack ?? 1),
  };
  state.dragPayload = payload;
  event.dataTransfer.setData("application/json", JSON.stringify(payload));
  event.dataTransfer.effectAllowed = "copy";
}

function onDragStartFromInventory(event) {
  const slot = event.currentTarget;
  if (!slot.dataset.itemData) {
    event.preventDefault();
    return;
  }
  state.dragSourceSlot = slot;
  state.dragDropped = false;

  const payload = {
    source: "inventory",
    slotType: slot.dataset.slotType,
    slotIndex: slot.dataset.slotIndex,
    tabIndex: slot.dataset.tabIndex,
    loadoutIndex: slot.dataset.loadoutIndex,
    itemData: slot.dataset.itemData,
  };
  state.dragPayload = payload;
  event.dataTransfer.setData("application/json", JSON.stringify(payload));
  event.dataTransfer.effectAllowed = "move";
}

function getDragPayload(event) {
  const data = event.dataTransfer?.getData("application/json");
  if (!data) {
    return state.dragPayload;
  }
  try {
    return JSON.parse(data);
  } catch (error) {
    return state.dragPayload;
  }
}

function onSlotDragOver(event) {
  const slot = event.currentTarget;
  const payload = getDragPayload(event);
  const allowed = canPlaceItem(slot, payload);
  slot.classList.toggle("drag-allowed", allowed);
  slot.classList.toggle("drag-blocked", !allowed);
  if (allowed) {
    event.preventDefault();
  }
}

function onSlotDragLeave(event) {
  const slot = event.currentTarget;
  slot.classList.remove("drag-allowed", "drag-blocked");
}

function onSlotDrop(event) {
  const slot = event.currentTarget;
  slot.classList.remove("drag-allowed", "drag-blocked");
  const payload = getDragPayload(event);
  if (!payload) {
    return;
  }
  if (!canPlaceItem(slot, payload)) {
    return;
  }
  if (payload.source === "catalog") {
    const maxStack = Number(payload.maxStack ?? 1);
    const count = maxStack > 1 ? 1 : undefined;
    updateSlotItem(slot, buildCatalogItem(payload.itemData, count));
    state.dragPayload = null;
    clearDragHighlights();
    return;
  }

  if (payload.source === "inventory") {
    const sourceSlot = findSlotFromPayload(payload);
    if (!sourceSlot) {
      return;
    }
    if (sourceSlot === slot) {
      state.dragDropped = true;
      state.dragPayload = null;
      clearDragHighlights();
      return;
    }
    const sourceItem = getSlotItem(sourceSlot);
    if (!sourceItem) {
      return;
    }
    const targetItem = getSlotItem(slot);
    updateSlotItem(sourceSlot, targetItem ?? null);
    updateSlotItem(slot, sourceItem);
    state.dragDropped = true;
    state.dragPayload = null;
    clearDragHighlights();
  }
}

function findSlotFromPayload(payload) {
  if (payload.slotType === "action") {
    return document.querySelector(
      `[data-slot-type="action"][data-slot-index="${payload.slotIndex}"]`
    );
  }
  if (payload.slotType === "personal") {
    return document.querySelector(
      `[data-slot-type="personal"][data-slot-index="${payload.slotIndex}"]`
    );
  }
  if (payload.slotType === "tabbed") {
    return document.querySelector(
      `[data-slot-type="tabbed"][data-tab-index="${payload.tabIndex}"]`
    );
  }
  if (payload.slotType === "loadout") {
    return document.querySelector(
      `[data-slot-type="loadout"][data-loadout-index="${payload.loadoutIndex}"]`
    );
  }
  return null;
}

function getSlotItem(slot) {
  const slotType = slot.dataset.slotType;
  if (slotType === "personal") {
    const index = Number(slot.dataset.slotIndex);
    return state.personalInventory[index];
  }
  if (slotType === "loadout") {
    const index = Number(slot.dataset.loadoutIndex);
    return state.loadout[index];
  }
  const index = getInventorySlotIndex(slot);
  return index !== null ? state.inventory[index] : null;
}

function onSlotDoubleClick(event) {
  const slot = event.currentTarget;
  const item = getSlotItem(slot);
  if (!item) {
    return;
  }
  const meta = state.catalogIndex.get(item.ItemData);
  const maxStack = meta?.maxStack ?? 1;
  if (maxStack <= 1) {
    return;
  }
  openCountModal(slot, maxStack, item.Count ?? 1);
}

function getTabSlotRange(tabKey) {
  const start = TAB_OFFSETS[tabKey];
  if (typeof start !== "number") {
    return null;
  }
  return { start, end: start + 23 };
}

function findNextAvailableSlot(tabKey) {
  const range = getTabSlotRange(tabKey);
  if (!range) {
    return null;
  }
  for (let i = range.start; i <= range.end; i += 1) {
    if (!state.inventory[i]) {
      return i;
    }
  }
  return null;
}

function buildCatalogItem(itemData, count) {
  const item = {
    GUID: generateGuid(),
    ItemData: itemData,
  };
  const meta = state.catalogIndex.get(itemData);
  if (meta?.baseDurability !== undefined && meta.baseDurability !== null) {
    item.Durability = meta.baseDurability;
  }
  if (shouldIncludeVitalShield(itemData)) {
    item.VitalShield = 0;
  }
  if (count && count > 1) {
    item.Count = count;
  }
  return item;
}

function addCatalogItemToNextSlot(itemData, useMax) {
  if (!itemData) {
    return;
  }
  const meta = state.catalogIndex.get(itemData);
  const maxStack = meta?.maxStack ?? 1;
  const count = useMax ? maxStack : maxStack > 1 ? 1 : undefined;
  const nextSlot = findNextAvailableSlot(state.activeTab);
  if (nextSlot === null) {
    openAlert("No available slots in the current inventory tab.");
    return;
  }
  const slot = document.querySelector(
    `[data-slot-type="tabbed"][data-tab-index="${nextSlot - TAB_OFFSETS[state.activeTab]}"]`
  );
  if (!slot) {
    openAlert("No available slots in the current inventory tab.");
    return;
  }
  updateSlotItem(slot, buildCatalogItem(itemData, count));
}

function onBrowserDoubleClick(event) {
  const slot = event.currentTarget;
  const itemData = slot.dataset.itemData;
  if (!itemData) {
    return;
  }
  addCatalogItemToNextSlot(itemData, false);
}

function buildTooltipData(data) {
  if (!data) {
    return null;
  }
  return {
    name: data.name ?? "",
    description: data.description ?? "",
    weight: data.weight,
    baseDurability: data.baseDurability,
    maxStack: data.maxStack,
    powerLevel: data.powerLevel,
    currentDurability: data.currentDurability,
  };
}

function setTooltipContent(data) {
  if (!tooltip || !tooltipName || !tooltipDesc || !tooltipMeta || !data) {
    return;
  }
  tooltipName.innerHTML = "";
  const nameIconWrap = document.createElement("div");
  nameIconWrap.className = "tooltip__icon tooltip__icon--power";
  const nameIcon = document.createElement("img");
  const hasPowerLevel =
    typeof data.powerLevel !== "undefined" && data.powerLevel !== null;
  nameIcon.src = hasPowerLevel
    ? "/shared/game-ui/ToolTip/PowerLevel.png"
    : "/shared/game-ui/ToolTip/no_power_level.png";
  nameIcon.alt = "";
  nameIconWrap.appendChild(nameIcon);
  if (hasPowerLevel) {
    const text = document.createElement("div");
    text.className = "tooltip__icon-text";
    text.textContent = String(data.powerLevel);
    nameIconWrap.appendChild(text);
  }
  tooltipName.appendChild(nameIconWrap);
  const nameText = document.createElement("div");
  nameText.textContent = data.name || "Item";
  tooltipName.appendChild(nameText);
  tooltipDesc.textContent = data.description || "";
  tooltipMeta.innerHTML = "";
  const rows = [];
  if (typeof data.weight !== "undefined") {
    rows.push({
      icon: "/shared/game-ui/ToolTip/Weight.png",
      value: data.weight,
      showIconText: false,
    });
  }
  if (
    typeof data.baseDurability !== "undefined" ||
    typeof data.currentDurability !== "undefined"
  ) {
    let durabilityValue = data.baseDurability;
    if (typeof data.currentDurability !== "undefined") {
      durabilityValue =
        typeof data.baseDurability !== "undefined"
          ? `${data.currentDurability}/${data.baseDurability}`
          : data.currentDurability;
    }
    rows.push({
      icon: "/shared/game-ui/ToolTip/Durability.png",
      value: durabilityValue,
      showIconText: false,
    });
  }
  if (typeof data.maxStack !== "undefined") {
    rows.push({
      icon: "/shared/game-ui/ToolTip/MaxStacks.png",
      value: data.maxStack,
      showIconText: false,
    });
  }
  rows.forEach((row) => {
    const line = document.createElement("div");
    line.className = "tooltip__row";
    const iconWrap = document.createElement("div");
    const iconClass =
      row.icon === "/shared/game-ui/ToolTip/Durability.png"
        ? "tooltip__icon tooltip__icon--durability"
        : "tooltip__icon";
    iconWrap.className = iconClass;
    const icon = document.createElement("img");
    icon.src = row.icon;
    icon.alt = "";
    iconWrap.appendChild(icon);
    if (row.showIconText && row.value !== null && row.value !== undefined) {
      const text = document.createElement("div");
      text.className = "tooltip__icon-text";
      text.textContent = String(row.value);
      iconWrap.appendChild(text);
    }
    line.appendChild(iconWrap);
    const value = document.createElement("div");
    value.textContent = row.value !== null && row.value !== undefined ? String(row.value) : "";
    line.appendChild(value);
    tooltipMeta.appendChild(line);
  });
}

function showTooltip(data, event) {
  if (!tooltip) {
    return;
  }
  setTooltipContent(data);
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

function onBrowserMouseEnter(event) {
  const slot = event.currentTarget;
  const data = buildTooltipData({
    name: slot.dataset.itemName,
    description: slot.dataset.description ?? "",
    weight: slot.dataset.weight ? Number(slot.dataset.weight) : undefined,
    baseDurability: slot.dataset.baseDurability
      ? Number(slot.dataset.baseDurability)
      : undefined,
    powerLevel: slot.dataset.powerLevel
      ? Number(slot.dataset.powerLevel)
      : undefined,
    maxStack: slot.dataset.maxStack ? Number(slot.dataset.maxStack) : undefined,
  });
  showTooltip(data, event);
}

function onSlotContextMenu(event) {
  event.preventDefault();
  const slot = event.currentTarget;
  if (!slot.dataset.itemData) {
    return;
  }
  state.contextSlot = slot;
  state.contextSource = "inventory";
  if (contextMenu) {
    configureContextMenu(["set-max", "dupe", "repair", "remove"]);
    const item = getSlotItem(slot);
    const meta = state.catalogIndex.get(slot.dataset.itemData);
    const maxStack = meta?.maxStack ?? 1;
    const hasDurability =
      typeof meta?.baseDurability !== "undefined" ||
      typeof item?.Durability !== "undefined";
    const slotType = slot.dataset.slotType;
    const canDupe = slotType !== "action" && slotType !== "loadout";
    setContextMenuActionVisible("set-max", maxStack > 1);
    setContextMenuActionVisible("dupe", canDupe);
    setContextMenuActionVisible("repair", hasDurability);
    contextMenu.classList.remove("hidden");
    contextMenu.style.left = `${event.clientX}px`;
    contextMenu.style.top = `${event.clientY}px`;
  }
}

function onBrowserContextMenu(event) {
  event.preventDefault();
  const slot = event.currentTarget;
  if (!slot.dataset.itemData) {
    return;
  }
  state.contextSlot = slot;
  state.contextSource = "browser";
  if (contextMenu) {
    configureContextMenu(["add", "add-max"]);
    contextMenu.classList.remove("hidden");
    contextMenu.style.left = `${event.clientX}px`;
    contextMenu.style.top = `${event.clientY}px`;
  }
}

function configureContextMenu(actions) {
  if (!contextMenu) {
    return;
  }
  const items = contextMenu.querySelectorAll("button[data-action]");
  items.forEach((button) => {
    const action = button.dataset.action;
    const shouldShow = actions.includes(action);
    button.classList.toggle("hidden", !shouldShow);
  });
}

function setContextMenuActionVisible(action, visible) {
  if (!contextMenu) {
    return;
  }
  const button = contextMenu.querySelector(`button[data-action="${action}"]`);
  if (button) {
    button.classList.toggle("hidden", !visible);
  }
}

function attachSlotHandlers() {
  const allSlots = [
    ...actionSlots,
    ...tabbedSlots,
    ...personalSlots,
    ...loadoutSlots,
  ];
  allSlots.forEach((slot) => {
    slot.addEventListener("dragstart", onDragStartFromInventory);
    slot.addEventListener("dragend", onInventoryDragEnd);
    slot.addEventListener("dragover", onSlotDragOver);
    slot.addEventListener("dragleave", onSlotDragLeave);
    slot.addEventListener("drop", onSlotDrop);
    slot.addEventListener("dblclick", onSlotDoubleClick);
    slot.addEventListener("contextmenu", onSlotContextMenu);
    slot.addEventListener("mouseenter", onInventoryMouseEnter);
    slot.addEventListener("mousemove", onTooltipMove);
    slot.addEventListener("mouseleave", hideTooltip);
    slot.draggable = true;
  });
}

function onInventoryMouseEnter(event) {
  const slot = event.currentTarget;
  if (!slot.dataset.itemData) {
    return;
  }
  const item = getSlotItem(slot);
  const meta = state.catalogIndex.get(slot.dataset.itemData);
  if (!meta) {
    return;
  }
  const data = buildTooltipData({
    ...meta,
    currentDurability:
      item && typeof item.Durability !== "undefined" ? item.Durability : undefined,
  });
  showTooltip(data, event);
}

function clearDragHighlights() {
  const allSlots = [
    ...actionSlots,
    ...tabbedSlots,
    ...personalSlots,
    ...loadoutSlots,
  ];
  allSlots.forEach((slot) => {
    slot.classList.remove("drag-allowed", "drag-blocked");
  });
}

function onInventoryDragEnd() {
  if (!state.dragSourceSlot) {
    return;
  }
  if (!state.dragDropped) {
    updateSlotItem(state.dragSourceSlot, null);
  }
  state.dragSourceSlot = null;
  state.dragDropped = false;
  state.dragPayload = null;
  clearDragHighlights();
}

function hideContextMenu() {
  if (!contextMenu) {
    return;
  }
  contextMenu.classList.add("hidden");
  state.contextSlot = null;
  state.contextSource = null;
}

function setMaxOnSlot(slot) {
  const item = getSlotItem(slot);
  if (!item) {
    return;
  }
  const meta = state.catalogIndex.get(item.ItemData);
  const maxStack = meta?.maxStack ?? 1;
  if (maxStack <= 1) {
    item.Count = undefined;
  } else {
    item.Count = maxStack;
  }
  updateSlotItem(slot, item);
}

function repairSlot(slot) {
  const item = getSlotItem(slot);
  if (!item) {
    return;
  }
  const meta = state.catalogIndex.get(item.ItemData);
  if (!meta || typeof meta.baseDurability === "undefined") {
    return;
  }
  item.Durability = meta.baseDurability;
  updateSlotItem(slot, item);
}

function findNextAvailableSlotForSection(slot) {
  const slotType = slot.dataset.slotType;
  if (slotType === "action") {
    for (let i = 0; i <= 7; i += 1) {
      if (!state.inventory[i]) {
        return { slotType: "action", slotIndex: i };
      }
    }
    return null;
  }
  if (slotType === "tabbed") {
    const range = getTabSlotRange(state.activeTab);
    if (!range) {
      return null;
    }
    for (let i = range.start; i <= range.end; i += 1) {
      if (!state.inventory[i]) {
        return {
          slotType: "tabbed",
          slotIndex: i,
          tabIndex: i - range.start,
        };
      }
    }
    return null;
  }
  if (slotType === "personal") {
    for (let i = 0; i <= SLOT_LIMITS.personal; i += 1) {
      if (!state.personalInventory[i]) {
        return { slotType: "personal", slotIndex: i };
      }
    }
    return null;
  }
  if (slotType === "loadout") {
    for (let i = 0; i <= SLOT_LIMITS.loadout; i += 1) {
      if (!state.loadout[i]) {
        return { slotType: "loadout", slotIndex: i };
      }
    }
    return null;
  }
  return null;
}

function duplicateSlotItem(slot) {
  const item = getSlotItem(slot);
  if (!item) {
    return;
  }
  const target = findNextAvailableSlotForSection(slot);
  if (!target) {
    return;
  }
  const clone = { ...item, GUID: generateGuid() };
  let targetSlot = null;
  if (target.slotType === "action") {
    targetSlot = document.querySelector(
      `[data-slot-type="action"][data-slot-index="${target.slotIndex}"]`
    );
  } else if (target.slotType === "tabbed") {
    targetSlot = document.querySelector(
      `[data-slot-type="tabbed"][data-tab-index="${target.tabIndex}"]`
    );
  } else if (target.slotType === "personal") {
    targetSlot = document.querySelector(
      `[data-slot-type="personal"][data-slot-index="${target.slotIndex}"]`
    );
  } else if (target.slotType === "loadout") {
    targetSlot = document.querySelector(
      `[data-slot-type="loadout"][data-loadout-index="${target.slotIndex}"]`
    );
  }
  if (!targetSlot) {
    return;
  }
  updateSlotItem(targetSlot, clone);
}

function openCountModal(slot, maxStack, current) {
  if (!countModal || !countInput || !countHint) {
    return;
  }
  state.modalSlot = slot;
  countInput.value = String(current);
  countInput.min = "1";
  countInput.removeAttribute("max");
  countHint.textContent = `Max: ${maxStack}`;
  countModal.classList.remove("hidden");
  countInput.focus();
}

function closeCountModal() {
  if (!countModal) {
    return;
  }
  countModal.classList.add("hidden");
  state.modalSlot = null;
}

function openAlert(message) {
  if (!alertModal || !alertMessage) {
    setStatus(message);
    return;
  }
  alertMessage.textContent = message;
  alertModal.classList.remove("hidden");
}

function closeAlert() {
  if (!alertModal) {
    return;
  }
  alertModal.classList.add("hidden");
}

function parseInventorySection(section) {
  const result = {};
  if (!section) {
    return result;
  }
  Object.entries(section).forEach(([key, value]) => {
    if (key === "MaxSlotIndex") {
      return;
    }
    const slotIndex = Number(key);
    if (!Number.isNaN(slotIndex)) {
      result[slotIndex] = value;
    }
  });
  return result;
}

function handleCharacterFile(text) {
  try {
    const data = JSON.parse(text);
    state.characterSource = data;
    state.inventory = parseInventorySection(data.Inventory);
    state.personalInventory = parseInventorySection(data.PersonalInventory);
    state.loadout = parseInventorySection(data.Loadout);
    setLoadUiState(true);
    setStatus("Character loaded. Inventory slots are now visible.");
    renderInventory();
  } catch (error) {
    setLoadUiState(false);
    setStatus("Failed to parse character JSON.");
  }
}

function buildExportData() {
  if (!state.characterSource) {
    return null;
  }
  const clone = JSON.parse(JSON.stringify(state.characterSource));
  const inventorySection = buildInventorySection(
    state.inventory,
    clone.Inventory,
    SLOT_LIMITS.inventory
  );
  const highestInventorySlot = getHighestSlotIndex(state.inventory);
  const existingInventoryMax = Number(inventorySection.MaxSlotIndex ?? 0);
  const nextInventoryMax = Math.max(existingInventoryMax, highestInventorySlot);
  inventorySection.MaxSlotIndex = Math.min(SLOT_LIMITS.inventory, nextInventoryMax);
  clone.Inventory = inventorySection;
  clone.PersonalInventory = buildPersonalInventorySection(
    state.personalInventory,
    clone.PersonalInventory,
    SLOT_LIMITS.personal
  );
  clone.Loadout = buildInventorySection(state.loadout, clone.Loadout, SLOT_LIMITS.loadout);
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
  const backupName = state.fileName
    ? state.fileName.replace(/\.json$/i, "") + "_backup.json"
    : "character_backup.json";
  const saveName = state.fileName ?? "character.json";

  if (state.fileHandle && "createWritable" in state.fileHandle) {
    try {
      const originalFile = await state.fileHandle.getFile();
      const originalText = await originalFile.text();
      const originalData = JSON.parse(originalText);
      downloadJsonFile(originalData, backupName);
      const writable = await state.fileHandle.createWritable();
      await writable.write(JSON.stringify(updated, null, 2));
      await writable.close();
      setStatus("Saved. Backup downloaded.");
      return;
    } catch (error) {
      setStatus("Save failed. Downloading files instead.");
    }
  }

  downloadJsonFile(updated, saveName);
  setStatus("Saved as download. Backup not written to disk.");
}

function buildInventorySection(source, existing, maxSlotIndex) {
  const section = {};
  Object.entries(source).forEach(([key, value]) => {
    section[key] = value;
  });
  if (existing && typeof existing.MaxSlotIndex !== "undefined") {
    section.MaxSlotIndex = existing.MaxSlotIndex;
  } else {
    section.MaxSlotIndex = maxSlotIndex;
  }
  return section;
}

function buildPersonalInventorySection(source, existing, maxSlotIndex) {
  const section = buildInventorySection(source, existing, maxSlotIndex);
  const keys = Object.keys(source)
    .map((key) => Number(key))
    .filter((value) => !Number.isNaN(value));
  const highest = keys.length ? Math.max(...keys) : 0;
  section.MaxSlotIndex = Math.min(maxSlotIndex, highest);
  return section;
}

function getHighestSlotIndex(source) {
  const keys = Object.keys(source ?? {})
    .map((key) => Number(key))
    .filter((value) => !Number.isNaN(value));
  if (!keys.length) {
    return 0;
  }
  return Math.max(...keys);
}

function setActiveTab(tabKey) {
  const config = TAB_CONFIG[tabKey];
  if (!config) {
    return;
  }

  state.activeTab = tabKey;
  state.pageIndex = 0;

  tabButtons.forEach((button) => {
    const key = button.dataset.tab;
    const image = button.querySelector("[data-tab-image]");
    const isActive = key === tabKey;
    button.setAttribute("aria-selected", String(isActive));
    image.src = isActive ? TAB_CONFIG[key].selected : TAB_CONFIG[key].normal;
  });

  itembrowserTitle.textContent = config.label;
  document.body.dataset.activeTab = tabKey;
  renderBagCategories();
  renderItemBrowser();
  renderInventory();
}

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setActiveTab(button.dataset.tab);
  });
});

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
      state.fileHandle = handle;
      state.fileName = file.name;
      const text = await file.text();
      handleCharacterFile(text);
      setStatus("Loaded via file picker. Save will overwrite this file.");
      return;
    } catch (error) {
      return;
    }
  }
  characterInput?.click();
}

if (characterInput) {
  characterInput.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    state.fileHandle = null;
    state.fileName = file.name;
    file.text().then(handleCharacterFile);
  });
}

if (saveButton) {
  saveButton.addEventListener("click", saveCharacter);
}

if (loadButton) {
  loadButton.addEventListener("click", openCharacterFile);
}

setLoadUiState(false);

if (browserPrev) {
  browserPrev.addEventListener("click", () => {
    if (browserPrev.classList.contains("is-disabled")) {
      return;
    }
    if (state.pageIndex <= 0) {
      return;
    }
    state.pageIndex -= 1;
    renderItemBrowser();
  });
}

if (browserNext) {
  browserNext.addEventListener("click", () => {
    if (browserNext.classList.contains("is-disabled")) {
      return;
    }
    if (!state.catalog) {
      return;
    }
    const tabData = state.catalog.tabs[state.activeTab];
    if (!tabData) {
      return;
    }
    const totalItems = tabData.items?.length ?? 0;
    const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
    if (state.pageIndex >= totalPages - 1) {
      return;
    }
    state.pageIndex += 1;
    renderItemBrowser();
  });
}

if (itemSearch) {
  itemSearch.addEventListener("input", (event) => {
    state.searchQuery = event.target.value.trim();
    if (itemSearchClear) {
      itemSearchClear.classList.toggle("is-hidden", !state.searchQuery);
    }
    state.pageIndex = 0;
    renderItemBrowser();
  });
}

if (itemSearchClear && itemSearch) {
  itemSearchClear.addEventListener("click", () => {
    itemSearch.value = "";
    state.searchQuery = "";
    itemSearchClear.classList.add("is-hidden");
    state.pageIndex = 0;
    renderItemBrowser();
    itemSearch.focus();
  });
}

attachSlotHandlers();

if (contextMenu) {
  contextMenu.addEventListener("click", (event) => {
    const action = event.target?.dataset?.action;
    if (!action || !state.contextSlot) {
      return;
    }
    if (action === "remove" && state.contextSource === "inventory") {
      updateSlotItem(state.contextSlot, null);
    }
    if (action === "set-max" && state.contextSource === "inventory") {
      setMaxOnSlot(state.contextSlot);
    }
    if (action === "repair" && state.contextSource === "inventory") {
      repairSlot(state.contextSlot);
    }
    if (action === "dupe" && state.contextSource === "inventory") {
      duplicateSlotItem(state.contextSlot);
    }
    if (action === "add" && state.contextSource === "browser") {
      addCatalogItemToNextSlot(state.contextSlot.dataset.itemData, false);
    }
    if (action === "add-max" && state.contextSource === "browser") {
      addCatalogItemToNextSlot(state.contextSlot.dataset.itemData, true);
    }
    hideContextMenu();
  });
}

document.addEventListener("click", (event) => {
  if (contextMenu && !contextMenu.contains(event.target)) {
    hideContextMenu();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    hideContextMenu();
    closeCountModal();
  }
});

if (countCancel) {
  countCancel.addEventListener("click", closeCountModal);
}

if (countApply) {
  const applyCount = () => {
    if (!state.modalSlot || !countInput) {
      return;
    }
    const item = getSlotItem(state.modalSlot);
    if (!item) {
      closeCountModal();
      return;
    }
    const raw = Number(countInput.value || 1);
    const parsed = Number.isNaN(raw) ? 1 : Math.max(1, Math.floor(raw));
    item.Count = parsed;
    updateSlotItem(state.modalSlot, item);
    closeCountModal();
  };
  countApply.addEventListener("click", applyCount);
  if (countInput) {
    countInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyCount();
      }
    });
  }
}

if (alertOk) {
  alertOk.addEventListener("click", closeAlert);
}

if (countModal) {
  countModal.addEventListener("click", (event) => {
    if (event.target === countModal) {
      closeCountModal();
    }
  });
}

fetch("/tools/item-editor/data/catalog.json")
  .then((response) => response.json())
  .then((catalog) => {
    state.catalog = normalizeCatalogPaths(catalog);
    state.catalogIndex = buildCatalogIndex(catalog);
    renderBagCategories();
    setActiveTab(state.activeTab);
  })
  .catch(() => {
    itembrowserTitle.textContent = "Item catalog unavailable";
  });

