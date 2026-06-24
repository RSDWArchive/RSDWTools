const loadButton = document.getElementById("load-button");
const saveButton = document.getElementById("save-button");
const characterInput = document.getElementById("character-file");
const statusBar = document.querySelector(".status-bar");
const statusIcon = document.querySelector(".status-bar__icon");
const statusText = document.getElementById("status-text");
const playerNameInput = document.getElementById("player-name");
const characterTypeSelect = document.getElementById("character-type");
const characterGuidInput = document.getElementById("character-guid");
const mountEquippedSelect = document.getElementById("mount-equipped");
const mapUnlockedSelect = document.getElementById("map-unlocked");
const skillsGrid = document.getElementById("skills-grid");
const mountList = document.getElementById("mount-list");
const vendorReputationGrid = document.getElementById("vendor-reputation-grid");
let skillInputs = Array.from(document.querySelectorAll("[data-skill-id]"));
let mountInputs = Array.from(document.querySelectorAll("[data-mount-value]"));
let vendorReputationInputs = Array.from(
  document.querySelectorAll("[data-vendor-reputation]")
);
const customizationInputs = Array.from(
  document.querySelectorAll("[data-customization]")
);
const upkeepTiles = Array.from(document.querySelectorAll(".upkeep-tile"));
const upkeepContextMenu = document.getElementById("upkeep-context-menu");

const INFINITE_BUFFER = 100000000;
const MAP_UNLOCKED_VALUE = 2147483647;
const CHARACTER_TYPE_VALUES = new Set(["0", "1", "2", "3"]);
const CHARACTER_TYPE_ICONS = {
  "0": "/shared/game-ui/Character/Standard.png",
  "1": "/shared/game-ui/Character/Hardcore.png",
  "2": "/shared/game-ui/Character/Creative.png",
  "3": "/shared/game-ui/Character/Custom.png",
};

let characterSource = null;
let characterFileName = null;
let characterFileHandle = null;
let activeUpkeep = null;
let customizationCatalog = null;
let pendingCustomization = null;
let skillXpById = new Map();
let unlockedMountValues = new Set();
let equippedMountValue = "";
let vendorReputationByTag = new Map();

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

function toIntegerDisplay(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0";
  }
  return String(Math.floor(Number(value)));
}

function isObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function gameProgressRoot(data) {
  return isObject(data?.GameProgress) ? data.GameProgress : null;
}

function characterHost(data) {
  if (!isObject(data)) {
    return null;
  }
  const gameProgress = gameProgressRoot(data);
  if (isObject(gameProgress?.Character)) {
    return gameProgress;
  }
  if (isObject(data.Character)) {
    return data;
  }
  return gameProgress || data;
}

function findCharacterRoot(data) {
  return characterHost(data)?.Character || null;
}

function ensureCharacterRoot(target) {
  const host = characterHost(target) || target;
  if (!isObject(host.Character)) {
    host.Character = {};
  }
  return host.Character;
}

function customizationHost(data) {
  if (!isObject(data)) {
    return null;
  }
  const gameProgress = gameProgressRoot(data);
  if (isObject(data.Customization)) {
    return data;
  }
  if (isObject(gameProgress?.Customization)) {
    return gameProgress;
  }
  if (isObject(gameProgress?.Character?.Customization)) {
    return gameProgress.Character;
  }
  if (isObject(data.Character?.Customization)) {
    return data.Character;
  }
  if (isObject(data.Character) && !gameProgress) {
    return data.Character;
  }
  return data;
}

function findCustomization(data) {
  return customizationHost(data)?.Customization?.CustomizationData || null;
}

function findUpkeep(data, key) {
  return findCharacterRoot(data)?.[key] || null;
}

function revealedFogHost(data) {
  if (!isObject(data)) {
    return null;
  }
  const gameProgress = gameProgressRoot(data);
  if (isObject(gameProgress?.RevealedFog)) {
    return gameProgress;
  }
  if (isObject(data.RevealedFog)) {
    return data;
  }
  return gameProgress || data;
}

function findRevealedFog(data) {
  return revealedFogHost(data)?.RevealedFog || null;
}

function skillsHost(data) {
  if (!isObject(data)) {
    return null;
  }
  const gameProgress = gameProgressRoot(data);
  if (isObject(gameProgress?.Skills)) {
    return gameProgress;
  }
  if (isObject(data.Skills)) {
    return data;
  }
  return gameProgress || data;
}

function findSkills(data) {
  return skillsHost(data)?.Skills?.Skills || null;
}

function findMount(data) {
  return findCharacterRoot(data)?.Mount || null;
}

function progressHost(data) {
  if (!isObject(data)) {
    return null;
  }
  const gameProgress = gameProgressRoot(data);
  if (isObject(gameProgress?.Progress)) {
    return gameProgress;
  }
  if (isObject(data.Progress)) {
    return data;
  }
  return gameProgress || data;
}

function findProgress(data) {
  return progressHost(data)?.Progress || null;
}

function ensureProgressRoot(target) {
  const host = progressHost(target) || target;
  if (!isObject(host.Progress)) {
    host.Progress = {};
  }
  return host.Progress;
}

function findVendorReputations(data) {
  return findProgress(data)?.VendorReputations || null;
}

function catalogMountValues() {
  const mounts = customizationCatalog?.Mounts;
  if (!Array.isArray(mounts)) {
    return new Set();
  }
  return new Set(
    mounts
      .map((mount) => mount?.save_value)
      .filter((value) => typeof value === "string" && value)
  );
}

function applySkillValuesToInputs() {
  skillInputs.forEach((input) => {
    const id = input.dataset.skillId;
    const xp = id ? skillXpById.get(id) : undefined;
    input.value = toIntegerDisplay(xp);
  });
}

function applyMountValuesToInputs() {
  mountInputs.forEach((input) => {
    const value = input.dataset.mountValue;
    input.checked = Boolean(value && unlockedMountValues.has(value));
  });
  if (!mountEquippedSelect) {
    return;
  }
  if (
    equippedMountValue &&
    !Array.from(mountEquippedSelect.options).some(
      (option) => option.value === equippedMountValue
    )
  ) {
    const option = document.createElement("option");
    option.value = equippedMountValue;
    option.textContent = `Unknown - ${equippedMountValue}`;
    mountEquippedSelect.appendChild(option);
  }
  mountEquippedSelect.value = equippedMountValue;
}

function applyVendorReputationValuesToInputs() {
  vendorReputationInputs.forEach((select) => {
    const tag = select.dataset.vendorReputation;
    const amount = tag ? vendorReputationByTag.get(tag) : undefined;
    setSelectValue(select, toIntegerDisplay(amount));
  });
}

function applyUpkeepDisplay(tile, data) {
  const valueSpan = tile.querySelector("[data-upkeep-value]");
  const value = data?.[`${tile.dataset.upkeep}Value`];
  const decay = data?.[`${tile.dataset.upkeep}DecayBuffer`];
  if (valueSpan) {
    valueSpan.textContent = toIntegerDisplay(value);
  }
  tile.dataset.value = String(Math.floor(Number(value ?? 0)));
  tile.dataset.decayBuffer = String(Number(decay ?? 0));
  tile.classList.toggle("is-infinite", decay === INFINITE_BUFFER);
}

function handleCharacterFile(text) {
  try {
    const data = JSON.parse(text);
    characterSource = data;
    if (playerNameInput) {
      playerNameInput.value = data?.meta_data?.char_name ?? "";
    }
    if (characterTypeSelect) {
      const rawType = data?.meta_data?.char_type;
      const parsed =
        typeof rawType === "number" ? rawType : Number(rawType ?? 0);
      const value = CHARACTER_TYPE_VALUES.has(String(parsed))
        ? String(parsed)
        : "0";
      characterTypeSelect.value = value;
      setCharacterTypeIcon(value);
    }
    if (characterGuidInput) {
      characterGuidInput.value = data?.meta_data?.char_guid ?? "";
    }
    const mount = findMount(data) || {};
    unlockedMountValues = new Set(
      Array.isArray(mount.MountsUnlockedList)
        ? mount.MountsUnlockedList.filter((value) => typeof value === "string")
        : []
    );
    equippedMountValue =
      typeof mount.MountEquipped === "string" ? mount.MountEquipped : "";
    applyMountValuesToInputs();
    if (mapUnlockedSelect) {
      const revealed = findRevealedFog(data)?.RevealedRegionsBitmap;
      const isUnlocked = Number(revealed) === MAP_UNLOCKED_VALUE;
      mapUnlockedSelect.value = isUnlocked ? "true" : "false";
    }
    const customization = findCustomization(data) || {};
    pendingCustomization = {};
    customizationInputs.forEach((input) => {
      const key = input.dataset.customization;
      const value = customization?.[key]?.rowName ?? "";
      if (key) {
        pendingCustomization[key] = value;
      }
      setSelectValue(input, value);
    });

    upkeepTiles.forEach((tile) => {
      const key = tile.dataset.upkeep;
      const upkeep = findUpkeep(data, key) || {};
      applyUpkeepDisplay(tile, upkeep);
    });

    const skills = findSkills(data) || [];
    skillXpById = new Map(
      skills
        .filter((skill) => skill && typeof skill.Id === "string")
        .map((skill) => [skill.Id, skill.Xp])
    );
    applySkillValuesToInputs();

    const vendorReputations = findVendorReputations(data) || [];
    vendorReputationByTag = new Map(
      Array.isArray(vendorReputations)
        ? vendorReputations
            .filter((row) => row && typeof row.VendorReputationTag === "string")
            .map((row) => [
              row.VendorReputationTag,
              parseNonNegativeInt(row.VendorReputationAmount),
            ])
        : []
    );
    applyVendorReputationValuesToInputs();
    setStatus("Character loaded.", true);
  } catch (error) {
    setStatus("Failed to parse character JSON.", false);
  }
}

function setCharacterTypeIcon(value) {
  if (!characterTypeSelect) {
    return;
  }
  const icon = CHARACTER_TYPE_ICONS[value] ?? CHARACTER_TYPE_ICONS["0"];
  characterTypeSelect.style.setProperty(
    "--character-type-icon",
    `url("${icon}")`
  );
}

function normalizeCharacterGuid(value) {
  const sanitized = String(value ?? "")
    .toUpperCase()
    .replace(/[^0-9A-F]/g, "")
    .slice(0, 32);
  if (!sanitized) {
    return "";
  }
  return sanitized.padStart(32, "0");
}

function setSelectValue(select, value) {
  if (!select) {
    return;
  }
  if (!Array.from(select.options).some((option) => option.value === value)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value || "Unknown";
    select.appendChild(option);
  }
  select.value = value;
}

function skillIconSrc(skill) {
  const icon = skill?.icon;
  if (typeof icon === "string" && icon) {
    return icon.startsWith("/") ? icon : `/shared/icons/${icon}`;
  }
  const name = skill?.display_name;
  if (typeof name === "string" && name) {
    return `/shared/game-ui/Character/${encodeURIComponent(name)}.png`;
  }
  return "/shared/game-ui/T_Icon_Placeholder.png";
}

function mountIconSrc(mount) {
  const icon = mount?.icon;
  if (typeof icon === "string" && icon) {
    return icon.startsWith("/") ? icon : `/shared/icons/${icon}`;
  }
  return "/shared/game-ui/T_Icon_Placeholder.png";
}

function bindSkillInput(input) {
  if (!input || input.dataset.skillBound === "true") {
    return;
  }
  input.dataset.skillBound = "true";
  input.addEventListener("input", () => {
    const raw = Number(input.value ?? 0);
    if (!Number.isFinite(raw)) {
      return;
    }
    if (raw < 0) {
      input.value = "0";
      return;
    }
    if (!Number.isInteger(raw)) {
      input.value = String(Math.floor(raw));
    }
  });
  input.addEventListener("blur", () => normalizeSkillInput(input));
}

function bindSkillInputs() {
  skillInputs.forEach(bindSkillInput);
}

function captureCurrentSkillValues() {
  skillInputs.forEach((input) => {
    const id = input.dataset.skillId;
    if (id) {
      skillXpById.set(id, parseNonNegativeInt(input.value));
    }
  });
}

function renderSkillCatalog() {
  const skills = customizationCatalog?.Skills;
  if (!skillsGrid || !Array.isArray(skills) || !skills.length) {
    return;
  }
  captureCurrentSkillValues();
  skillsGrid.innerHTML = "";
  skills.forEach((skill) => {
    if (!skill?.id) {
      return;
    }
    const label = document.createElement("label");
    label.className = "character-field";

    const labelText = document.createElement("span");
    labelText.className = "skill-label";

    const icon = document.createElement("img");
    icon.className = "skill-icon";
    icon.src = skillIconSrc(skill);
    icon.alt = "";
    labelText.appendChild(icon);
    labelText.append(skill.display_name || skill.internal_name || skill.id);

    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.step = "1";
    input.inputMode = "numeric";
    input.dataset.skillId = skill.id;

    label.appendChild(labelText);
    label.appendChild(input);
    skillsGrid.appendChild(label);
  });
  skillInputs = Array.from(document.querySelectorAll("[data-skill-id]"));
  bindSkillInputs();
  applySkillValuesToInputs();
}

function renderMountCatalog() {
  const mounts = customizationCatalog?.Mounts;
  if (!Array.isArray(mounts)) {
    return;
  }
  if (mountEquippedSelect) {
    mountEquippedSelect.innerHTML = "";
    const noneOption = document.createElement("option");
    noneOption.value = "";
    noneOption.textContent = "None";
    mountEquippedSelect.appendChild(noneOption);
    mounts.forEach((mount) => {
      if (!mount?.save_value) {
        return;
      }
      const option = document.createElement("option");
      option.value = mount.save_value;
      option.textContent = mount.display_name || mount.internal_name;
      mountEquippedSelect.appendChild(option);
    });
  }
  if (mountList) {
    mountList.innerHTML = "";
    mounts.forEach((mount) => {
      if (!mount?.save_value) {
        return;
      }
      const label = document.createElement("label");
      label.className = "mount-toggle";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.dataset.mountValue = mount.save_value;
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          unlockedMountValues.add(mount.save_value);
        } else {
          unlockedMountValues.delete(mount.save_value);
        }
      });
      label.appendChild(checkbox);

      const icon = document.createElement("img");
      icon.className = "mount-icon";
      icon.src = mountIconSrc(mount);
      icon.alt = "";
      label.appendChild(icon);

      const content = document.createElement("span");
      content.className = "mount-label";
      const name = document.createElement("span");
      name.className = "mount-name";
      name.textContent = mount.display_name || mount.internal_name || "Mount";
      content.appendChild(name);
      const meta = document.createElement("span");
      meta.className = "mount-meta";
      meta.textContent = mount.mount_type || mount.internal_name || mount.save_value;
      content.appendChild(meta);
      label.appendChild(content);
      mountList.appendChild(label);
    });
    mountInputs = Array.from(document.querySelectorAll("[data-mount-value]"));
  }
  applyMountValuesToInputs();
}

function renderVendorReputationCatalog() {
  const reputations = customizationCatalog?.VendorReputations;
  if (!vendorReputationGrid || !Array.isArray(reputations)) {
    return;
  }
  vendorReputationGrid.innerHTML = "";
  reputations.forEach((reputation) => {
    if (!reputation?.tag) {
      return;
    }
    const label = document.createElement("label");
    label.className = "character-field";
    const labelText = document.createElement("span");
    labelText.textContent = reputation.display_name || reputation.tag;
    label.appendChild(labelText);

    const select = document.createElement("select");
    select.dataset.vendorReputation = reputation.tag;
    const tiers = Array.isArray(reputation.tiers) && reputation.tiers.length
      ? reputation.tiers
      : [0, 1000, 2000, 3000];
    tiers.forEach((tier) => {
      const value = toIntegerDisplay(tier);
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    label.appendChild(select);
    vendorReputationGrid.appendChild(label);
  });
  vendorReputationInputs = Array.from(
    document.querySelectorAll("[data-vendor-reputation]")
  );
  applyVendorReputationValuesToInputs();
}

function populateCustomizationOptions() {
  if (!customizationCatalog) {
    return;
  }
  customizationInputs.forEach((select) => {
    const key = select.dataset.customization;
    if (!key) {
      return;
    }
    const options = customizationCatalog[key] || [];
    select.innerHTML = "";
    options.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    const pendingValue = pendingCustomization?.[key] ?? "";
    if (pendingValue) {
      setSelectValue(select, pendingValue);
    }
  });
}

async function loadCustomizationCatalog() {
  try {
    const response = await fetch("/tools/character-editor/data/character_catalog.json", {
      cache: "no-store",
    });
    customizationCatalog = await response.json();
    renderSkillCatalog();
    renderMountCatalog();
    renderVendorReputationCatalog();
    populateCustomizationOptions();
  } catch (error) {
    console.error(error);
  }
}

function setCustomizationRowName(target, key, value) {
  const host = customizationHost(target) || target;
  if (!isObject(host.Customization)) {
    host.Customization = {};
  }
  if (!isObject(host.Customization.CustomizationData)) {
    host.Customization.CustomizationData = {};
  }
  if (!isObject(host.Customization.CustomizationData[key])) {
    host.Customization.CustomizationData[key] = { rowName: value };
  } else {
    host.Customization.CustomizationData[key].rowName = value;
  }
}

function setUpkeepValue(target, key, value, decayBuffer) {
  const character = ensureCharacterRoot(target);
  if (!isObject(character[key])) {
    character[key] = {};
  }
  character[key][`${key}Value`] = value;
  if (typeof decayBuffer !== "undefined") {
    character[key][`${key}DecayBuffer`] = decayBuffer;
  }
}

function ensureMountRoot(target) {
  const character = ensureCharacterRoot(target);
  if (!isObject(character.Mount)) {
    character.Mount = {};
  }
  return character.Mount;
}

function setMountState(target) {
  const mount = ensureMountRoot(target);
  const knownCatalogValues = catalogMountValues();
  const selected = mountInputs
    .filter((input) => input.checked && input.dataset.mountValue)
    .map((input) => input.dataset.mountValue);
  unlockedMountValues.forEach((value) => {
    if (!knownCatalogValues.has(value)) {
      selected.push(value);
    }
  });
  const equipped = mountEquippedSelect?.value || "";
  if (equipped) {
    selected.push(equipped);
    mount.MountEquipped = equipped;
  } else {
    delete mount.MountEquipped;
  }
  mount.MountsUnlockedList = Array.from(new Set(selected));
}

function setMapUnlocked(target, isUnlocked) {
  const host = revealedFogHost(target) || target;
  if (!isObject(host.RevealedFog)) {
    host.RevealedFog = {};
  }
  if (isUnlocked) {
    host.RevealedFog.RevealedRegionsBitmap = MAP_UNLOCKED_VALUE;
  }
}

function ensureSkillsContainer(target) {
  const host = skillsHost(target) || target;
  if (!isObject(host.Skills)) {
    host.Skills = {};
  }
  if (!Array.isArray(host.Skills.Skills)) {
    host.Skills.Skills = [];
  }
  return host.Skills.Skills;
}

function setVendorReputations(target) {
  const progress = ensureProgressRoot(target);
  const knownTags = new Set(
    vendorReputationInputs
      .map((input) => input.dataset.vendorReputation)
      .filter((tag) => typeof tag === "string" && tag)
  );
  const existing = Array.isArray(progress.VendorReputations)
    ? progress.VendorReputations.filter(
        (row) =>
          row &&
          typeof row.VendorReputationTag === "string" &&
          !knownTags.has(row.VendorReputationTag)
      )
    : [];

  vendorReputationInputs.forEach((input) => {
    const tag = input.dataset.vendorReputation;
    if (!tag) {
      return;
    }
    const amount = parseNonNegativeInt(input.value);
    if (amount > 0) {
      existing.push({
        VendorReputationTag: tag,
        VendorReputationAmount: amount,
      });
    }
  });
  progress.VendorReputations = existing;
}

function parseNonNegativeInt(value) {
  const parsed = Math.floor(Number(value ?? 0));
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0;
  }
  return parsed;
}

function normalizeSkillInput(input) {
  if (!input) {
    return;
  }
  const nextValue = parseNonNegativeInt(input.value);
  input.value = String(nextValue);
}

function buildExportData() {
  if (!characterSource) {
    return null;
  }
  const clone = JSON.parse(JSON.stringify(characterSource));
  if (playerNameInput) {
    if (!clone.meta_data) {
      clone.meta_data = {};
    }
    clone.meta_data.char_name = playerNameInput.value ?? "";
  }
  if (characterTypeSelect) {
    if (!clone.meta_data) {
      clone.meta_data = {};
    }
    const parsed = Number(characterTypeSelect.value ?? 0);
    clone.meta_data.char_type = Number.isNaN(parsed) ? 0 : parsed;
  }
  if (characterGuidInput) {
    if (!clone.meta_data) {
      clone.meta_data = {};
    }
    clone.meta_data.char_guid = normalizeCharacterGuid(
      characterGuidInput.value
    );
  }
  customizationInputs.forEach((input) => {
    const key = input.dataset.customization;
    if (!key) {
      return;
    }
    setCustomizationRowName(clone, key, input.value ?? "");
  });

  upkeepTiles.forEach((tile) => {
    const key = tile.dataset.upkeep;
    const valueSpan = tile.querySelector("[data-upkeep-value]");
    const value = Number(tile.dataset.value ?? valueSpan?.textContent ?? 0);
    const decay = Number(tile.dataset.decayBuffer ?? 0);
    setUpkeepValue(clone, key, value, decay);
  });

  if (mountEquippedSelect || mountInputs.length) {
    setMountState(clone);
  }
  if (mapUnlockedSelect) {
    const isUnlocked = mapUnlockedSelect.value === "true";
    setMapUnlocked(clone, isUnlocked);
  }
  if (vendorReputationInputs.length) {
    setVendorReputations(clone);
  }

  if (skillInputs.length) {
    const list = ensureSkillsContainer(clone);
    const index = new Map(
      list
        .filter((skill) => skill && typeof skill.Id === "string")
        .map((skill) => [skill.Id, skill])
    );
    skillInputs.forEach((input) => {
      const id = input.dataset.skillId;
      if (!id) {
        return;
      }
      const xp = parseNonNegativeInt(input.value);
      const existing = index.get(id);
      if (existing) {
        existing.Xp = xp;
      } else {
        list.push({ Id: id, Xp: xp });
      }
    });
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

function openUpkeepMenu(event, tile) {
  if (!upkeepContextMenu) {
    return;
  }
  event.preventDefault();
  activeUpkeep = tile;
  upkeepContextMenu.style.left = `${event.clientX}px`;
  upkeepContextMenu.style.top = `${event.clientY}px`;
  upkeepContextMenu.classList.remove("hidden");
}

function closeUpkeepMenu() {
  if (!upkeepContextMenu) {
    return;
  }
  upkeepContextMenu.classList.add("hidden");
  activeUpkeep = null;
}

function updateUpkeepTile(tile, action) {
  if (!tile) {
    return;
  }
  const valueSpan = tile.querySelector("[data-upkeep-value]");
  if (!valueSpan) {
    return;
  }
  let value = Number(tile.dataset.value ?? valueSpan.textContent ?? 0);
  let decay = Number(tile.dataset.decayBuffer ?? 0);
  if (action === "set-max") {
    value = 100;
  } else if (action === "set-infinite") {
    value = 100;
    decay = INFINITE_BUFFER;
  } else if (action === "remove-infinite") {
    decay = 0;
  }
  valueSpan.textContent = String(Math.floor(value));
  tile.dataset.value = String(Math.floor(value));
  tile.dataset.decayBuffer = String(decay);
  tile.classList.toggle("is-infinite", decay === INFINITE_BUFFER);
}

function bindEvents() {
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
  if (characterGuidInput) {
    characterGuidInput.addEventListener("input", () => {
      const sanitized = String(characterGuidInput.value ?? "")
        .toUpperCase()
        .replace(/[^0-9A-F]/g, "")
        .slice(0, 32);
      characterGuidInput.value = sanitized;
    });
    characterGuidInput.addEventListener("blur", () => {
      characterGuidInput.value = normalizeCharacterGuid(
        characterGuidInput.value
      );
    });
  }
  bindSkillInputs();
  if (characterTypeSelect) {
    characterTypeSelect.addEventListener("change", (event) => {
      setCharacterTypeIcon(event.target.value);
    });
  }
  if (mountEquippedSelect) {
    mountEquippedSelect.addEventListener("change", () => {
      equippedMountValue = mountEquippedSelect.value || "";
      if (equippedMountValue) {
        unlockedMountValues.add(equippedMountValue);
      }
      applyMountValuesToInputs();
    });
  }
  upkeepTiles.forEach((tile) => {
    tile.addEventListener("contextmenu", (event) => openUpkeepMenu(event, tile));
  });
  if (upkeepContextMenu) {
    upkeepContextMenu.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) {
        return;
      }
      if (activeUpkeep) {
        updateUpkeepTile(activeUpkeep, target.dataset.action);
      }
      closeUpkeepMenu();
    });
    window.addEventListener("click", (event) => {
      if (!upkeepContextMenu.classList.contains("hidden") && !upkeepContextMenu.contains(event.target)) {
        closeUpkeepMenu();
      }
    });
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeUpkeepMenu();
      }
    });
  }
}

setStatus("Load a character file to edit player data.", false);
bindEvents();
loadCustomizationCatalog();
setCharacterTypeIcon(characterTypeSelect?.value ?? "0");
