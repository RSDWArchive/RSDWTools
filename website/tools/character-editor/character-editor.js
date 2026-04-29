const loadButton = document.getElementById("load-button");
const saveButton = document.getElementById("save-button");
const characterInput = document.getElementById("character-file");
const statusBar = document.querySelector(".status-bar");
const statusIcon = document.querySelector(".status-bar__icon");
const statusText = document.getElementById("status-text");
const playerNameInput = document.getElementById("player-name");
const characterTypeSelect = document.getElementById("character-type");
const characterGuidInput = document.getElementById("character-guid");
const mountUnlockedSelect = document.getElementById("mount-unlocked");
const mapUnlockedSelect = document.getElementById("map-unlocked");
const skillInputs = Array.from(document.querySelectorAll("[data-skill-id]"));
const customizationInputs = Array.from(
  document.querySelectorAll("[data-customization]")
);
const upkeepTiles = Array.from(document.querySelectorAll(".upkeep-tile"));
const upkeepContextMenu = document.getElementById("upkeep-context-menu");

const INFINITE_BUFFER = 100000000;
const MAP_UNLOCKED_VALUE = 65535;
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

function findCharacterRoot(data) {
  return data?.Character || null;
}

function findCustomization(data) {
  return data?.Character?.Customization?.CustomizationData || null;
}

function findUpkeep(data, key) {
  return data?.Character?.[key] || null;
}

function findSkills(data) {
  return data?.Skills?.Skills || null;
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
    if (mountUnlockedSelect) {
      const mountUnlocked = Boolean(data?.Character?.Mount?.MountUnlocked);
      mountUnlockedSelect.value = mountUnlocked ? "true" : "false";
    }
    if (mapUnlockedSelect) {
      const revealed = data?.RevealedFog?.RevealedRegionsBitmap;
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
    const skillMap = new Map(
      skills
        .filter((skill) => skill && typeof skill.Id === "string")
        .map((skill) => [skill.Id, skill.Xp])
    );
    skillInputs.forEach((input) => {
      const id = input.dataset.skillId;
      const xp = id ? skillMap.get(id) : undefined;
      input.value = toIntegerDisplay(xp);
    });
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
    const response = await fetch("/tools/character-editor/data/character_catalog.json");
    customizationCatalog = await response.json();
    populateCustomizationOptions();
  } catch (error) {
    console.error(error);
  }
}

function setCustomizationRowName(target, key, value) {
  if (!target.Character) {
    target.Character = {};
  }
  if (!target.Character.Customization) {
    target.Character.Customization = {};
  }
  if (!target.Character.Customization.CustomizationData) {
    target.Character.Customization.CustomizationData = {};
  }
  if (!target.Character.Customization.CustomizationData[key]) {
    target.Character.Customization.CustomizationData[key] = { rowName: value };
  } else {
    target.Character.Customization.CustomizationData[key].rowName = value;
  }
}

function setUpkeepValue(target, key, value, decayBuffer) {
  if (!target.Character) {
    target.Character = {};
  }
  if (!target.Character[key]) {
    target.Character[key] = {};
  }
  target.Character[key][`${key}Value`] = value;
  if (typeof decayBuffer !== "undefined") {
    target.Character[key][`${key}DecayBuffer`] = decayBuffer;
  }
}

function setMountUnlocked(target, value) {
  if (!target.Character) {
    target.Character = {};
  }
  if (!target.Character.Mount) {
    target.Character.Mount = {};
  }
  target.Character.Mount.MountUnlocked = Boolean(value);
}

function setMapUnlocked(target, isUnlocked) {
  if (!target.RevealedFog) {
    target.RevealedFog = {};
  }
  if (isUnlocked) {
    target.RevealedFog.RevealedRegionsBitmap = MAP_UNLOCKED_VALUE;
  }
}

function ensureSkillsContainer(target) {
  if (!target.Skills) {
    target.Skills = {};
  }
  if (!Array.isArray(target.Skills.Skills)) {
    target.Skills.Skills = [];
  }
  return target.Skills.Skills;
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

  if (mountUnlockedSelect) {
    setMountUnlocked(clone, mountUnlockedSelect.value === "true");
  }
  if (mapUnlockedSelect) {
    const isUnlocked = mapUnlockedSelect.value === "true";
    setMapUnlocked(clone, isUnlocked);
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
  skillInputs.forEach((input) => {
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
  });
  if (characterTypeSelect) {
    characterTypeSelect.addEventListener("change", (event) => {
      setCharacterTypeIcon(event.target.value);
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