const questTitle = document.getElementById("quest-title");
const questSearchInput = document.getElementById("quest-search");
const questSearchClear = document.getElementById("quest-search-clear");
const mainQuestList = document.getElementById("main-quest-list");
const sideQuestList = document.getElementById("side-quest-list");
const statusBar = document.querySelector(".status-bar");
const statusIcon = document.querySelector(".status-bar__icon");
const statusText = document.getElementById("status-text");
const loadButton = document.getElementById("load-button");
const saveButton = document.getElementById("save-button");
const characterInput = document.getElementById("character-file");

const QUESTS_URL = "/tools/quest-editor/data/quests.json";

let allQuests = [];
let filteredQuests = [];
let characterSource = null;
let characterFileName = null;
let characterFileHandle = null;
let completedQuestIds = new Set();
let pendingQuestIds = new Set();

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

function questId(quest) {
  return quest.persistence_id || "";
}

function isComplete(quest) {
  return completedQuestIds.has(questId(quest));
}

function isPending(quest) {
  return pendingQuestIds.has(questId(quest));
}

function checkedCount() {
  return completedQuestIds.size + pendingQuestIds.size;
}

function characterName() {
  return characterSource?.meta_data?.char_name || characterFileName || "Character";
}

function updateTitle() {
  if (!questTitle) {
    return;
  }
  const total = allQuests.length;
  const filtered = filteredQuests.length;
  if (filtered === total) {
    questTitle.textContent = `All Quests (${total})`;
  } else {
    questTitle.textContent = `Quests (${filtered} of ${total})`;
  }
}

function updateLoadedStatus(prefix) {
  if (!characterSource) {
    setStatus("Load a character file to view quest completion.", false);
    return;
  }
  const total = allQuests.length;
  const complete = checkedCount();
  const pending = pendingQuestIds.size;
  const suffix = pending
    ? `${complete}/${total} complete, ${pending} pending save`
    : `${complete}/${total} complete`;
  setStatus(`${prefix || characterName()}: ${suffix}`, true);
}

function rowSubtitle(quest) {
  if (quest.duplicate_display_name) {
    return `${quest.internal_name} - ${quest.persistence_id}`;
  }
  return quest.internal_name || quest.persistence_id;
}

function renderQuestRow(quest) {
  const row = document.createElement("label");
  row.className = "quest-row";
  const id = questId(quest);
  const complete = isComplete(quest);
  const pending = isPending(quest);
  row.classList.toggle("quest-row--complete", complete);
  row.classList.toggle("quest-row--pending", pending);

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = complete || pending;
  checkbox.disabled = complete || !characterSource;
  checkbox.dataset.questId = id;
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) {
      pendingQuestIds.add(id);
    } else {
      pendingQuestIds.delete(id);
    }
    renderQuestLists();
    updateLoadedStatus(characterName());
  });
  row.appendChild(checkbox);

  const content = document.createElement("span");
  content.className = "quest-row__content";

  const name = document.createElement("span");
  name.className = "quest-row__name";
  name.textContent = quest.display_name || quest.internal_name || "Quest";
  content.appendChild(name);

  const meta = document.createElement("span");
  meta.className = "quest-row__meta";
  meta.textContent = rowSubtitle(quest);
  content.appendChild(meta);

  row.appendChild(content);

  const state = document.createElement("span");
  state.className = "quest-row__state";
  state.textContent = complete ? "Complete" : pending ? "Pending" : "Incomplete";
  row.appendChild(state);

  return row;
}

function renderGroup(container, quests, emptyText) {
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!quests.length) {
    const empty = document.createElement("div");
    empty.className = "quest-list__empty";
    empty.textContent = emptyText;
    container.appendChild(empty);
    return;
  }
  quests.forEach((quest) => {
    container.appendChild(renderQuestRow(quest));
  });
}

function renderQuestLists() {
  const mainQuests = filteredQuests.filter((quest) => quest.is_main_quest);
  const sideQuests = filteredQuests.filter((quest) => !quest.is_main_quest);
  renderGroup(mainQuestList, mainQuests, "No main quests match.");
  renderGroup(sideQuestList, sideQuests, "No side quests match.");
  updateTitle();
}

function applyFilter(query) {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    filteredQuests = [...allQuests];
  } else {
    filteredQuests = allQuests.filter((quest) => {
      const values = [
        quest.display_name,
        quest.internal_name,
        quest.persistence_id,
        quest.quest_region,
      ];
      return values.some((value) =>
        String(value || "").toLowerCase().includes(needle)
      );
    });
  }
  renderQuestLists();
}

function readCompletedQuestIds(data) {
  const quests = data?.QuestProgress?.Quests;
  if (!Array.isArray(quests)) {
    return new Set();
  }
  const ids = new Set();
  quests.forEach((row) => {
    if (row && typeof row === "object" && Number(row.QuestState) === 2 && row.QuestId) {
      ids.add(row.QuestId);
    }
  });
  return ids;
}

function ensureQuestProgress(data) {
  if (!data.QuestProgress || typeof data.QuestProgress !== "object") {
    data.QuestProgress = {};
  }
  if (!Array.isArray(data.QuestProgress.Quests)) {
    data.QuestProgress.Quests = [];
  }
  return data.QuestProgress.Quests;
}

function minimalCompletedQuestRow(id) {
  return {
    QuestId: id,
    QuestState: 2,
    QuestObjective: "None",
    QuestInts: [],
    QuestBools: [],
  };
}

function buildExportData() {
  if (!characterSource) {
    return null;
  }
  const clone = JSON.parse(JSON.stringify(characterSource));
  const questRows = ensureQuestProgress(clone);

  pendingQuestIds.forEach((id) => {
    const matches = questRows.filter(
      (row) => row && typeof row === "object" && row.QuestId === id
    );
    if (matches.length) {
      matches.forEach((row) => {
        row.QuestState = 2;
      });
    } else {
      questRows.push(minimalCompletedQuestRow(id));
    }
  });

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

function acceptSavedData(data, message) {
  characterSource = data;
  completedQuestIds = readCompletedQuestIds(data);
  pendingQuestIds = new Set();
  renderQuestLists();
  updateLoadedStatus(message);
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
      acceptSavedData(updated, "Saved");
      return;
    } catch (error) {
      setStatus("Save failed. Downloading files instead.", true);
    }
  }

  downloadJsonFile(updated, saveName);
  acceptSavedData(updated, "Saved as download");
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
      updateLoadedStatus("Loaded via file picker");
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
    completedQuestIds = readCompletedQuestIds(data);
    pendingQuestIds = new Set();
    renderQuestLists();
    updateLoadedStatus(characterName());
  } catch (error) {
    setStatus("Failed to parse character JSON.", false);
  }
}

function bindControls() {
  if (questSearchInput) {
    questSearchInput.addEventListener("input", () => {
      applyFilter(questSearchInput.value);
      if (questSearchClear) {
        questSearchClear.classList.toggle(
          "is-hidden",
          questSearchInput.value.length === 0
        );
      }
    });
  }
  if (questSearchClear) {
    questSearchClear.addEventListener("click", () => {
      if (!questSearchInput) {
        return;
      }
      questSearchInput.value = "";
      questSearchClear.classList.add("is-hidden");
      applyFilter("");
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
}

async function loadQuests() {
  try {
    const response = await fetch(QUESTS_URL);
    const payload = await response.json();
    allQuests = Array.isArray(payload.quests) ? payload.quests : [];
    filteredQuests = [...allQuests];
    renderQuestLists();
    updateLoadedStatus();
  } catch (error) {
    setStatus("Failed to load quest catalog.", false);
    console.error(error);
  }
}

setStatus("Load a character file to view quest completion.", false);
bindControls();
loadQuests();
