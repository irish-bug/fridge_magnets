(function () {
  "use strict";

  const topics = JSON.parse(document.getElementById("topics-data").textContent);
  const pool = document.getElementById("pool");
  const tileTemplate = document.getElementById("tile-template");
  const poolCount = document.getElementById("pool-count");
  const statusMessage = document.getElementById("status-message");
  const nameInput = document.getElementById("submitter-name");
  const submitBtn = document.getElementById("submit-btn");
  const resetBtn = document.getElementById("reset-btn");
  const detailEmpty = document.getElementById("detail-empty");
  const detailShort = document.getElementById("detail-short");
  const detailFull = document.getElementById("detail-full");

  const topicById = Object.fromEntries(topics.map((t) => [t.id, t]));

  function makeTile(topic) {
    const node = tileTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.topicId = topic.id;
    node.querySelector(".tile-short").textContent = topic.short;
    return node;
  }

  function buildPool() {
    pool.innerHTML = "";
    topics.forEach((topic) => pool.appendChild(makeTile(topic)));
    updatePoolCount();
  }

  function updatePoolCount() {
    const remaining = pool.children.length;
    poolCount.textContent = remaining > 0 ? `(${remaining} left to place)` : "(all placed)";
  }

  function setStatus(text, kind) {
    statusMessage.textContent = text;
    statusMessage.className = kind || "";
  }

  function showDetail(topic) {
    detailEmpty.classList.add("hidden");
    detailShort.classList.remove("hidden");
    detailFull.classList.remove("hidden");
    detailShort.textContent = topic.short;
    detailFull.textContent = topic.full;
  }

  document.addEventListener("pointerdown", (e) => {
    const tile = e.target.closest(".tile");
    if (!tile) return;
    const topic = topicById[tile.dataset.topicId];
    if (topic) showDetail(topic);
  });

  function initSortables() {
    new Sortable(pool, {
      group: "tiles",
      animation: 150,
      forceFallback: true,
      onSort: updatePoolCount,
      onAdd: updatePoolCount,
      onRemove: updatePoolCount,
    });

    document.querySelectorAll(".slot-dropzone").forEach((dropzone) => {
      new Sortable(dropzone, {
        group: {
          name: "tiles",
          put: (to) => to.el.children.length === 0,
        },
        animation: 150,
        forceFallback: true,
        onAdd: updatePoolCount,
        onRemove: updatePoolCount,
      });
    });
  }

  function moveAllTilesToPool() {
    document.querySelectorAll(".slot-dropzone .tile").forEach((tile) => {
      pool.appendChild(tile);
    });
    updatePoolCount();
  }

  function resetBoard() {
    moveAllTilesToPool();
    setStatus("", "");
  }

  function collectAssignments() {
    const assignments = {};
    let missing = 0;
    document.querySelectorAll(".slot-dropzone").forEach((dropzone) => {
      const tile = dropzone.querySelector(".tile");
      if (tile) {
        assignments[dropzone.dataset.slotId] = tile.dataset.topicId;
      } else {
        missing += 1;
      }
    });
    return { assignments, missing };
  }

  async function handleSubmit() {
    const name = nameInput.value.trim();
    if (!name) {
      setStatus("Please enter your name before submitting.", "error");
      nameInput.focus();
      return;
    }

    const { assignments, missing } = collectAssignments();
    if (missing > 0) {
      setStatus(`Place all topics first — ${missing} slot(s) still empty.`, "error");
      return;
    }

    submitBtn.disabled = true;
    setStatus("Submitting…", "");

    try {
      const response = await fetch("/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, assignments }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setStatus(data.error || "Something went wrong. Please try again.", "error");
        return;
      }

      setStatus(`Thanks, ${name}! Your schedule was saved.`, "success");
      nameInput.value = "";
      moveAllTilesToPool();
    } catch (err) {
      setStatus("Could not reach the server. Please try again.", "error");
    } finally {
      submitBtn.disabled = false;
    }
  }

  submitBtn.addEventListener("click", handleSubmit);
  resetBtn.addEventListener("click", resetBoard);

  buildPool();
  initSortables();
})();
