const $ = (id) => document.getElementById(id);
const state = {
  files: [],
  faceFiles: [],
  job: null,
  source: null,
  logs: [],
  currentStage: "queued",
  currentModelUrl: null
};

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 2600);
}

function renderFileThumbs(files, countId, thumbsId) {
  $(countId).textContent = files.length;
  const thumbs = $(thumbsId);
  thumbs.replaceChildren();
  files.slice(0, 20).forEach((file) => {
    const img = document.createElement("img");
    img.className = "thumb";
    img.alt = file.name;
    img.src = URL.createObjectURL(file);
    thumbs.appendChild(img);
  });
}

function setFiles(files) {
  state.files = Array.from(files || []);
  renderFileThumbs(state.files, "fileCount", "thumbs");
}

function setFaceFiles(files) {
  state.faceFiles = Array.from(files || []);
  renderFileThumbs(state.faceFiles, "faceFileCount", "faceThumbs");
}

function setProgress(stage, progress, status) {
  state.currentStage = stage || state.currentStage;
  $("stageLabel").textContent = (stage || "idle").replaceAll("_", " ");
  $("progressText").textContent = `${progress ?? 0}%`;
  $("progressBar").style.width = `${progress ?? 0}%`;
  $("jobStatus").textContent = (status || "idle").toUpperCase();

  const order = ["planning","viewforge","generating","judge","refinement","mesh_doctor","retopo","composite","gameprep","portable","qa"];
  const current = order.indexOf(stage);
  document.querySelectorAll("#stageStrip span").forEach((el) => {
    const idx = order.indexOf(el.dataset.stage);
    el.classList.toggle("active", idx === current);
    el.classList.toggle("done", current > idx || stage === "complete");
  });
}

function appendLog(line) {
  if (!line) return;
  state.logs.push(line);
  if (state.logs.length > 500) state.logs.shift();
  $("log").textContent = state.logs.join("\n");
  $("log").scrollTop = $("log").scrollHeight;
}

function syncAnimationControls() {
  const viewer = $("viewer");
  const controls = $("animationControls");
  const select = $("animationSelect");
  const clips = Array.from(viewer.availableAnimations || []);
  select.replaceChildren();
  if (!clips.length) {
    controls.hidden = true;
    $("animationMeta").textContent = "No animation clips";
    $("animationPlay").textContent = "Play";
    return;
  }
  clips.forEach((clip) => {
    const option = document.createElement("option");
    option.value = clip;
    option.textContent = clip;
    select.appendChild(option);
  });
  const preferred = clips.find((x) => /idle/i.test(x)) || clips[0];
  viewer.animationName = preferred;
  select.value = preferred;
  viewer.pause();
  controls.hidden = false;
  $("animationPlay").textContent = "Play";
  $("animationMeta").textContent = `${clips.length} clip${clips.length === 1 ? "" : "s"} ready`;
}

function showModel(url, label, meta="") {
  if (!url) return;
  const viewer = $("viewer");
  const sameModel = state.currentModelUrl === url && Boolean(viewer.src);
  $("modelLabel").textContent = label || "HAYUYA model";
  $("modelMeta").textContent = meta || "Interactive GLB";
  $("emptyState").style.display = "none";

  // Job polling runs every 3.5 seconds. Do not replace the same GLB on every
  // refresh: doing so resets the selected clip, playback time, camera state and
  // can flash the viewer while the user is inspecting a model.
  if (sameModel) return;

  state.currentModelUrl = url;
  $("viewerError").hidden = true;
  $("animationControls").hidden = true;
  viewer.pause();
  viewer.src = url;
}

function renderSemanticAnatomy(semantic) {
  const section = $("semanticSection");
  const summary = $("semanticSummary");
  const grid = $("semanticParts");
  if (!semantic) {
    section.hidden = true;
    summary.textContent = "";
    grid.replaceChildren();
    return;
  }

  section.hidden = false;
  const ready = Boolean(semantic.ready);
  $("semanticState").textContent = ready ? "PASS" : "BLOCKED";
  $("semanticState").className = ready ? "qa-state ready" : "qa-state blocked";

  const targets = Array.isArray(semantic.critical_targets)
    ? semantic.critical_targets
    : [];
  const aggregate = semantic.aggregate || {};
  const parts = Array.isArray(aggregate.parts) ? aggregate.parts : [];
  const missing = Array.isArray(aggregate.missing_parts)
    ? aggregate.missing_parts
    : [];
  const views = Array.isArray(semantic.rendered_views)
    ? semantic.rendered_views.length
    : 0;

  summary.textContent = [
    targets.length ? "targets " + targets.join(", ") : "no critical targets",
    views + " rendered views",
    missing.length ? "missing " + missing.join(", ") : "all required parts detected",
  ].join(" · ");

  grid.replaceChildren();
  parts.forEach((part) => {
    const item = document.createElement("div");
    item.className = "qa-chip " + (part.ready ? "pass" : "fail");
    const name = document.createElement("span");
    name.textContent = String(part.part || "part");
    const value = document.createElement("strong");
    const detectedViews = Number(part.detected_views || 0);
    const score = part.best_grounding_score == null
      ? ""
      : " · " + Number(part.best_grounding_score).toFixed(2);
    value.textContent = (part.ready ? "PASS" : "MISS") + " · " + detectedViews + " view" + (detectedViews === 1 ? "" : "s") + score;
    item.title = Array.isArray(part.views) ? part.views.join(" · ") : "";
    item.append(name, value);
    grid.appendChild(item);
  });

  if (!parts.length && semantic.error) {
    const item = document.createElement("div");
    item.className = "qa-chip fail";
    const name = document.createElement("span");
    name.textContent = "Semantic proof";
    const value = document.createElement("strong");
    value.textContent = "UNAVAILABLE";
    item.title = String(semantic.error);
    item.append(name, value);
    grid.appendChild(item);
  }
}

function renderPortablePack(pack) {
  const section = $("portableSection");
  const summary = $("portableSummary");
  const grid = $("portableTiers");
  if (!pack) {
    section.hidden = true;
    summary.textContent = "";
    grid.replaceChildren();
    return;
  }

  section.hidden = false;
  const complete = Boolean(pack.complete_lod_chain);
  const parityReady = Boolean(pack.lod_parity_ready);
  const budgetReady = Boolean(pack.runtime_budget_ready);
  const ready = complete && parityReady && budgetReady;
  $("portableState").textContent = ready ? "PASS" : "BLOCKED";
  $("portableState").className = ready ? "qa-state ready" : "qa-state blocked";
  const tiers = Array.isArray(pack.tiers) ? pack.tiers : [];
  summary.textContent = [
    tiers.length + " runtime tier" + (tiers.length === 1 ? "" : "s"),
    "LOD chain " + (complete ? "complete" : "incomplete"),
    "parity " + (parityReady ? "passed" : "blocked"),
    "budget " + (budgetReady ? "passed" : "blocked"),
  ].join(" · ");

  grid.replaceChildren();
  tiers.forEach((tier) => {
    const parity = tier?.lod_parity || {};
    const item = document.createElement("div");
    item.className = "qa-chip " + (parity.ready ? "pass" : "fail");
    const name = document.createElement("span");
    name.textContent = String(tier?.tier || "tier");
    const value = document.createElement("strong");
    const lodCount = Number(parity.lod_count || tier?.gameprep?.lods?.length || 0);
    value.textContent = (parity.ready ? "PASS" : "BLOCK") + " · " + lodCount + " LOD";
    const failures = Array.isArray(parity.errors) ? parity.errors.filter(Boolean) : [];
    item.title = failures.length
      ? failures.slice(0, 4).join(" · ")
      : "Hero Master parity passed";
    item.append(name, value);
    grid.appendChild(item);

    const budget = tier?.runtime_budget || {};
    const budgetChip = document.createElement("div");
    budgetChip.className = "qa-chip " + (budget.ready ? "pass" : "fail");
    const budgetName = document.createElement("span");
    budgetName.textContent = String(tier?.tier || "tier") + " budget";
    const budgetValue = document.createElement("strong");
    budgetValue.textContent = (budget.ready ? "PASS" : "BLOCK")
      + " · " + Number(budget.lod_count || 0) + " LOD";
    const budgetErrors = Array.isArray(budget.errors) ? budget.errors.filter(Boolean) : [];
    budgetChip.title = budgetErrors.length
      ? budgetErrors.slice(0, 4).join(" · ")
      : "triangle/material/texture house budgets passed";
    budgetChip.append(budgetName, budgetValue);
    grid.appendChild(budgetChip);

    const budgetItems = Array.isArray(budget.items) ? budget.items : [];
    budgetItems.forEach((lod) => {
      const row = document.createElement("div");
      row.className = "qa-chip " + (lod.ready ? "pass" : "fail");
      const label = document.createElement("span");
      label.textContent = String(tier?.tier || "tier") + " " + String(lod.name || "LOD") + " budget";
      const metric = document.createElement("strong");
      const parts = [];
      if (lod.faces != null && lod.face_budget_max != null) {
        parts.push(
          Number(lod.faces).toLocaleString()
          + "/" + Number(lod.face_budget_max).toLocaleString()
          + " tris"
        );
      }
      if (lod.material_count != null && lod.material_slots_max != null) {
        parts.push(
          Number(lod.material_count)
          + "/" + Number(lod.material_slots_max)
          + " mats"
        );
      }
      if (lod.texture_max_edge != null && lod.texture_edge_max != null) {
        parts.push(
          Number(lod.texture_max_edge)
          + "/" + Number(lod.texture_edge_max)
          + "px"
        );
      }
      metric.textContent = parts.join(" · ") || (lod.ready ? "PASS" : "BLOCK");
      row.title = Array.isArray(lod.errors) ? lod.errors.join(" · ") : "";
      row.append(label, metric);
      grid.appendChild(row);
    });

    const details = Array.isArray(parity.items) ? parity.items : [];
    details.forEach((lod) => {
      const row = document.createElement("div");
      row.className = "qa-chip " + (lod.ready ? "pass" : "fail");
      const label = document.createElement("span");
      label.textContent = String(tier?.tier || "tier") + " " + String(lod.name || "LOD");
      const metric = document.createElement("strong");
      const parts = [];
      if (lod.shape_p95_distance_ratio != null) {
        parts.push("shape " + Number(lod.shape_p95_distance_ratio).toFixed(3));
      }
      if (lod.faces != null) {
        parts.push(Number(lod.faces).toLocaleString() + " tris");
      }
      if (lod.attachment_components != null) {
        parts.push(Number(lod.attachment_components) + " parts");
      }
      if (lod.attachment_accessories != null) {
        parts.push(Number(lod.attachment_accessories) + " accessories");
      }
      if (lod.attachment_ready === false) {
        parts.push("attachment!");
      }
      if (lod.attachment_accessory_retention_ready === false) {
        parts.push("accessory loss!");
      }
      if (lod.rig_required) {
        parts.push(lod.rig_ready ? "rig" : "rig!");
        parts.push(lod.deformation_ready ? "deform" : "deform!");
      }
      metric.textContent = parts.join(" · ") || (lod.ready ? "PASS" : "BLOCK");
      row.title = Array.isArray(lod.errors) ? lod.errors.join(" · ") : "";
      row.append(label, metric);
      grid.appendChild(row);
    });
  });
}

function renderAAA(aaa) {
  const section = $("aaaSection");
  const summary = $("aaaSummary");
  const grid = $("aaaGates");
  const blockersBox = $("aaaBlockers");
  if (!aaa) {
    section.hidden = true;
    summary.textContent = "";
    grid.replaceChildren();
    blockersBox.replaceChildren();
    blockersBox.hidden = true;
    return;
  }

  section.hidden = false;
  const ready = Boolean(aaa.ready);
  $("aaaState").textContent = ready ? "PASS" : "BLOCKED";
  $("aaaState").className = ready ? "qa-state ready" : "qa-state blocked";
  const passed = Number(aaa.passed_required || 0);
  const total = Number(aaa.total_required || 0);
  summary.textContent = ready
    ? "Internal AAA contract passed · " + passed + "/" + total + " required gates"
    : "Internal AAA contract · " + passed + "/" + total + " required gates passed";

  grid.replaceChildren();
  const gates = Array.isArray(aaa.gates) ? aaa.gates : [];
  gates.filter((gate) => gate && gate.required).forEach((gate) => {
    const item = document.createElement("div");
    item.className = "qa-chip " + (gate.ready ? "pass" : "fail");
    const name = document.createElement("span");
    name.textContent = String(gate.id || "gate").replaceAll("_", " ");
    const value = document.createElement("strong");
    value.textContent = gate.ready ? "PASS" : "BLOCK";
    item.title = gate.evidence || "";
    item.append(name, value);
    grid.appendChild(item);
  });

  const blockers = Array.isArray(aaa.blockers) ? aaa.blockers.filter(Boolean) : [];
  blockersBox.replaceChildren();
  blockersBox.hidden = blockers.length === 0;
  blockers.slice(0, 12).forEach((blocker) => {
    const row = document.createElement("div");
    row.className = "qa-warning";
    const marker = document.createElement("span");
    marker.textContent = "!";
    const text = document.createElement("p");
    text.textContent = blocker;
    row.append(marker, text);
    blockersBox.appendChild(row);
  });
}
function renderFinalQa(qa) {
  const section = $("finalQaSection");
  const grid = $("finalQa");
  const warningsBox = $("finalQaWarnings");
  if (!qa) {
    section.hidden = true;
    grid.replaceChildren();
    warningsBox.replaceChildren();
    warningsBox.hidden = true;
    return;
  }

  section.hidden = false;
  $("finalQaState").textContent = qa.production_ready ? "READY" : "BLOCKED";
  $("finalQaState").className = qa.production_ready ? "qa-state ready" : "qa-state blocked";
  grid.replaceChildren();

  const items = [
    ["Production", qa.production_ready],
    ["Material", qa.material_ready],
    ["Texture", qa.texture_ready],
    ["Rebake", qa.rebake_ready],
    ["Rig", qa.rig_ready],
    ["Surface crossings", qa.crossing_ready],
    ["Self intersections", qa.self_intersection_ready],
    ["Composite attachments", qa.composite_attachment_ready],
    ["UV / Tangent", qa.uv_tangent_ready],
    ["Shading basis", qa.shading_basis_ready],
    ...(Number(qa.morph_targets || 0) > 0 ? [["Morphs", qa.morph_ready]] : []),
    ["SkinWeights", qa.skin_weights_ready],
    ["Animation", qa.animation_ready],
    ["Animation QA", qa.animation_integrity_ready],
    ["Deformation", qa.deformation_ready],
    ["Face refs", qa.face_ready],
    ["Face evidence", qa.face_quality_ready],
    ["Critical anatomy", qa.anatomy_ready],
  ];
  items.forEach(([label, ready]) => {
    const item = document.createElement("div");
    item.className = "qa-chip " + (ready ? "pass" : "fail");
    const name = document.createElement("span");
    name.textContent = label;
    const value = document.createElement("strong");
    value.textContent = ready ? "PASS" : "WAIT";
    item.append(name, value);
    grid.appendChild(item);
  });

  if (
    qa.morph_targets != null
    || qa.crossing_pairs != null
    || qa.self_intersection_pairs != null
    || qa.composite_components != null
    || qa.composite_accessories != null
    || qa.composite_floating != null
    || qa.composite_oversized_floating != null
  ) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Mesh dynamics";
    const value = document.createElement("strong");
    const parts = [];
    if (qa.morph_targets != null) {
      parts.push(Number(qa.morph_targets) + " morphs");
    }
    if (qa.crossing_pairs != null) {
      parts.push(Number(qa.crossing_pairs) + " crossings");
    }
    if (qa.self_intersection_pairs != null) {
      parts.push(Number(qa.self_intersection_pairs) + " self-crossings");
    }
    if (qa.composite_components != null) {
      parts.push(Number(qa.composite_components) + " components");
    }
    if (qa.composite_accessories != null) {
      parts.push(Number(qa.composite_accessories) + " accessories");
    }
    if (qa.composite_floating != null) {
      parts.push(Number(qa.composite_floating) + " floating");
    }
    if (qa.composite_oversized_floating != null) {
      parts.push(Number(qa.composite_oversized_floating) + " donor islands");
    }
    value.textContent = parts.join(" · ");
    item.append(name, value);
    grid.appendChild(item);
  }

  if (
    qa.uv_missing != null
    || qa.uv_degenerate != null
    || qa.shading_missing_normals != null
    || qa.shading_missing_tangents != null
    || qa.shading_bad_handedness != null
    || qa.shading_nonorthogonal != null
  ) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Shading topology";
    const value = document.createElement("strong");
    const parts = [];
    if (qa.uv_missing != null) {
      parts.push(Number(qa.uv_missing) + " missing UV");
    }
    if (qa.uv_degenerate != null) {
      parts.push(Number(qa.uv_degenerate) + " degenerate UV tris");
    }
    if (qa.shading_missing_normals != null) {
      parts.push(Number(qa.shading_missing_normals) + " missing normals");
    }
    if (qa.shading_missing_tangents != null) {
      parts.push(Number(qa.shading_missing_tangents) + " missing tangents");
    }
    if (qa.shading_bad_handedness != null) {
      parts.push(Number(qa.shading_bad_handedness) + " bad handedness");
    }
    if (qa.shading_nonorthogonal != null) {
      parts.push(Number(qa.shading_nonorthogonal) + " non-ortho");
    }
    value.textContent = parts.join(" · ");
    item.append(name, value);
    grid.appendChild(item);
  }

  if (qa.anatomy_expected != null || qa.anatomy_evaluated != null) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Anatomy refs";
    const value = document.createElement("strong");
    const evaluated = Number(qa.anatomy_evaluated || 0);
    const expected = Number(qa.anatomy_expected || 0);
    value.textContent = evaluated + "/" + expected + " judged";
    item.append(name, value);
    grid.appendChild(item);
  }

  if (qa.animation_channels != null || qa.animation_keyframes != null) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Animation data";
    const value = document.createElement("strong");
    const channels = Number(qa.animation_channels || 0);
    const keyframes = Number(qa.animation_keyframes || 0);
    value.textContent = channels + " ch · " + keyframes + " keys";
    item.append(name, value);
    grid.appendChild(item);
  }

  if (
    qa.deformation_frames != null
    || qa.deformation_max_disp != null
    || qa.deformation_max_edge != null
  ) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Deformation data";
    const value = document.createElement("strong");
    const parts = [];
    if (qa.deformation_frames != null) {
      parts.push(Number(qa.deformation_frames) + " poses");
    }
    if (qa.deformation_max_disp != null) {
      parts.push("disp " + Number(qa.deformation_max_disp).toFixed(2) + "×");
    }
    if (qa.deformation_max_edge != null) {
      parts.push("edge " + Number(qa.deformation_max_edge).toFixed(2) + "×");
    }
    value.textContent = parts.join(" · ");
    item.append(name, value);
    grid.appendChild(item);
  }

  const rebakeResolved = qa.rebaked_channels || [];
  const rebakePending = qa.rebake_pending_channels || [];
  if (rebakeResolved.length || rebakePending.length) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Material maps";
    const value = document.createElement("strong");
    const parts = [];
    if (rebakeResolved.length) parts.push("rebuilt " + rebakeResolved.join(" + "));
    if (rebakePending.length) parts.push("pending " + rebakePending.join(" + "));
    value.textContent = parts.join(" · ");
    item.append(name, value);
    grid.appendChild(item);
  }

  const textureActual = qa.basecolor_min || qa.basecolor_max;
  if (textureActual || qa.texture_target) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Visible texture";
    const value = document.createElement("strong");
    const actual = textureActual ? `${textureActual}px` : "unknown";
    const target = qa.texture_target ? `${qa.texture_target}px target` : "no target";
    value.textContent = `${actual} / ${target}`;
    item.append(name, value);
    grid.appendChild(item);
  }

  if (qa.face_expected != null && Number(qa.face_expected) > 0) {
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Face refs";
    const value = document.createElement("strong");
    value.textContent = `${Number(qa.face_evaluated || 0)}/${Number(qa.face_expected)}`;
    item.append(name, value);
    grid.appendChild(item);
  }

  [
    ["Texture score", qa.texture_score],
    ["Face score", qa.face_score],
    ["Face worst", qa.face_min],
    ["FaceMesh", qa.facemesh_score],
    ["FaceTex", qa.facetex_score],
    ["FaceDetail", qa.facedetail_score],
  ].forEach(([label, score]) => {
    if (score == null) return;
    const item = document.createElement("div");
    item.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = label;
    const value = document.createElement("strong");
    value.textContent = Number(score).toFixed(1);
    item.append(name, value);
    grid.appendChild(item);
  });

  const warnings = Array.isArray(qa.warnings) ? qa.warnings.filter(Boolean) : [];
  warningsBox.replaceChildren();
  warningsBox.hidden = warnings.length === 0;
  warnings.slice(0, 6).forEach((warning) => {
    const row = document.createElement("div");
    row.className = "qa-warning";
    const marker = document.createElement("span");
    marker.textContent = "!";
    const text = document.createElement("p");
    text.textContent = warning;
    row.append(marker, text);
    warningsBox.appendChild(row);
  });
}

function renderCompositePlan(plan, executions = []) {
  const section = $("compositeSection");
  const summary = $("compositeSummary");
  const grid = $("compositeDonors");
  if (!plan) {
    section.hidden = true;
    summary.textContent = "";
    grid.replaceChildren();
    return;
  }

  section.hidden = false;
  const required = Boolean(plan.composite_required);
  $("compositeState").textContent = required ? "MIX" : "BASE";
  $("compositeState").className = required ? "qa-state ready" : "qa-state";
  const finalists = Array.isArray(plan.finalist_backends) ? plan.finalist_backends.length : 0;
  summary.textContent = required
    ? "Base " + (plan.base_backend || "unknown") + " · " + finalists + " finalists · regional donors selected"
    : "Base " + (plan.base_backend || "unknown") + " already owns the strongest regional evidence";

  grid.replaceChildren();
  const donors = Array.isArray(plan.donors) ? plan.donors : [];
  donors.filter((item) => item && item.donor_backend).forEach((item) => {
    const chip = document.createElement("div");
    const isExternal = item.donor_backend !== plan.base_backend;
    chip.className = "qa-chip " + (isExternal ? "metric" : "pass");
    const name = document.createElement("span");
    name.textContent = String(item.region || "region").replaceAll("_", " ");
    const value = document.createElement("strong");
    const score = item.donor_score == null ? "" : " " + Number(item.donor_score).toFixed(1);
    value.textContent = String(item.donor_backend) + score;
    chip.title = (item.strategy || "retain") + " · seam " + (item.seam_risk || "?") + " · rig " + (item.rig_risk || "?");
    chip.append(name, value);
    grid.appendChild(chip);
  });

  const detailDonors = Array.isArray(plan.detail_donors) ? plan.detail_donors : [];
  detailDonors
    .filter((item) => item && item.donor_backend)
    .forEach((item) => {
      const chip = document.createElement("div");
      const token = "detail:" + String(item.source || "");
      const executable = Array.isArray(plan.executable_now) && plan.executable_now.includes(token);
      const external = item.donor_backend !== plan.base_backend;
      chip.className = "qa-chip " + (external ? (executable ? "pass" : "metric") : "pass");
      const name = document.createElement("span");
      const sourceName = String(item.source || "detail").split(/[\\/]/).pop() || "detail";
      name.textContent = sourceName;
      const value = document.createElement("strong");
      const region = item.region_hint ? String(item.region_hint) + " · " : "";
      const score = item.donor_score == null ? "" : " " + Number(item.donor_score).toFixed(1);
      value.textContent = region + String(item.donor_backend) + score;
      const accessoryMatch = item.accessory_match || {};
      const accessoryConfidence = accessoryMatch.ready
        ? Math.max(
            ...((accessoryMatch.matches || [])
              .filter((match) => match && match.ready && match.confidence != null)
              .map((match) => Number(match.confidence))),
            0
          )
        : null;
      const insertGeometryReady = accessoryMatch.rigged_insert_supported;
      const insertMaterialReady = accessoryMatch.rigged_insert_material_ready;
      const insertBlocker = accessoryMatch.rigged_insert_production_blocker;
      chip.title = (item.strategy || "local detail")
        + " · " + (executable ? "executable" : "guarded")
        + " · seam " + (item.seam_risk || "?")
        + (accessoryConfidence != null ? " · accessory match " + accessoryConfidence.toFixed(2) : "")
        + (insertGeometryReady != null
          ? " · geometry " + (insertGeometryReady ? "ready" : "blocked")
          : "")
        + (insertMaterialReady != null
          ? " · material " + (insertMaterialReady ? "ready" : "blocked")
          : "")
        + (insertBlocker ? " · " + String(insertBlocker) : "");
      chip.append(name, value);
      grid.appendChild(chip);
    });

  const executionItems = Array.isArray(executions) ? executions : [];
  executionItems.forEach((item) => {
    if (!item) return;
    const chip = document.createElement("div");
    chip.className = "qa-chip " + (item.status === "rejected" ? "fail" : "pass");
    const name = document.createElement("span");
    name.textContent = "Applied " + (item.source || item.region || "detail");
    const value = document.createElement("strong");
    const parts = [];
    if (item.region) parts.push(String(item.region));
    if (item.strategy) {
      parts.push(
        String(item.strategy).replaceAll("_", " ")
      );
    }
    if (item.accessory_confidence != null) {
      parts.push(
        "match " + Number(item.accessory_confidence).toFixed(2)
      );
    }
    if (item.changed_vertices != null) {
      parts.push(Number(item.changed_vertices) + " verts");
    }
    if (item.inserted_vertices != null) {
      parts.push(Number(item.inserted_vertices) + " new verts");
    }
    if (item.inserted_faces != null) {
      parts.push(Number(item.inserted_faces) + " new tris");
    }
    if (item.inserted_primitives != null) {
      parts.push(Number(item.inserted_primitives) + " prims");
    }
    if (item.material_groups != null) {
      parts.push(Number(item.material_groups) + " materials");
    }
    if (item.weight_transfer_vertices != null) {
      parts.push(Number(item.weight_transfer_vertices) + " weighted");
    }
    if (item.weight_source_max != null) {
      parts.push("weight radius " + Number(item.weight_source_max).toFixed(3));
    }
    if (item.surface_transfer && item.surface_transfer !== "none") {
      parts.push(String(item.surface_transfer).replaceAll("_", " "));
    }
    if (item.surface_fallback_vertices != null) {
      parts.push(
        Number(item.surface_fallback_vertices) === 0
          ? "surface exact"
          : Number(item.surface_fallback_vertices) + " surface fallback"
      );
    }
    if (item.surface_search_triangles != null) {
      parts.push(
        "surface search " + Number(item.surface_search_triangles) + " tris"
      );
    }
    if (item.surface_bvh_nodes != null) {
      parts.push(
        "BVH " + Number(item.surface_bvh_nodes) + " nodes"
      );
    }
    if (item.surface_ambiguous_vertices != null) {
      parts.push(
        Number(item.surface_ambiguous_vertices) === 0
          ? "surface unambiguous"
          : Number(item.surface_ambiguous_vertices) + " surface ambiguous!"
      );
    }
    if (item.surface_skin_gap != null) {
      parts.push(
        "skin gap " + Number(item.surface_skin_gap).toFixed(4)
      );
    }
    if (item.surface_skin_l1 != null) {
      parts.push(
        "skin L1 " + Number(item.surface_skin_l1).toFixed(2)
      );
    }
    if (item.morph_targets_transferred != null) {
      parts.push(Number(item.morph_targets_transferred) + " morph targets");
    }
    if (item.geometry_ready != null) {
      parts.push(item.geometry_ready ? "geometry" : "geometry!");
    }
    if (item.legacy_preserved != null) {
      parts.push(item.legacy_preserved ? "legacy exact" : "legacy!");
    } else if (item.runtime_preserved != null) {
      parts.push(item.runtime_preserved ? "runtime exact" : "runtime!");
    }
    if (item.rig_ready != null) {
      parts.push(item.rig_ready ? "rig" : "rig!");
    }
    if (item.skin_weights_ready != null) {
      parts.push(item.skin_weights_ready ? "skin" : "skin!");
    }
    if (item.morph_deformation_ready != null) {
      parts.push(
        item.morph_deformation_ready ? "morph" : "morph!"
      );
    }
    if (item.animation_ready != null) {
      parts.push(item.animation_ready ? "animation" : "animation!");
    }
    if (item.deformation_ready != null) {
      parts.push(item.deformation_ready ? "deform" : "deform!");
    }
    if (item.attachment_ready != null) {
      parts.push(item.attachment_ready ? "attached" : "attachment!");
    }
    if (item.material_ready != null) {
      parts.push(item.material_ready ? "PBR" : "PBR!");
    }
    if (item.uv_ready != null) {
      parts.push(item.uv_ready ? "UV" : "UV!");
    }
    if (item.uv_tangent_ready != null) {
      parts.push(item.uv_tangent_ready ? "tangent" : "tangent!");
    }
    if (Array.isArray(item.material_channels) && item.material_channels.length) {
      parts.push(item.material_channels.join("+"));
    }
    if (item.production_ready != null) {
      parts.push(item.production_ready ? "production" : "production!");
    }
    if (item.rebake_ready != null) {
      parts.push(item.rebake_ready ? "rebake" : "rebake!");
    }
    if (item.changed_fraction != null) {
      parts.push((Number(item.changed_fraction) * 100).toFixed(1) + "% atlas");
    }
    if (item.seam_p95 != null) {
      parts.push("seam " + Number(item.seam_p95).toFixed(1));
    }
    value.textContent = parts.join(" · ") || (item.donor || "detail");
    chip.title = "donor " + (item.donor || "?") + (item.seam_max != null ? " · seam max " + Number(item.seam_max).toFixed(1) : "");
    chip.append(name, value);
    grid.appendChild(chip);
  });

  const executable = Array.isArray(plan.executable_now) ? plan.executable_now : [];
  const deferred = Array.isArray(plan.deferred_transfers) ? plan.deferred_transfers : [];
  if (executable.length || deferred.length) {
    const detail = document.createElement("div");
    detail.className = "qa-chip metric";
    const name = document.createElement("span");
    name.textContent = "Transfer plan";
    const value = document.createElement("strong");
    value.textContent = [
      executable.length ? "safe " + executable.length : "",
      deferred.length ? "guarded " + deferred.length : "",
    ].filter(Boolean).join(" · ");
    detail.append(name, value);
    grid.appendChild(detail);
  }
}
function renderCandidates(job) {
  const list = $("candidates");
  const candidates = job?.candidates || [];
  $("candidateCount").textContent = candidates.length;
  list.replaceChildren();
  if (!candidates.length) {
    const empty = document.createElement("div");
    empty.className = "muted-card";
    empty.textContent = "Candidates will appear here.";
    list.appendChild(empty);
    return;
  }
  candidates.forEach((candidate) => {
    const card = document.createElement("div");
    card.className = "candidate-card";
    const row = document.createElement("div");
    row.className = "card-row";
    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = candidate.label;
    if (candidate.is_champion) {
      const crown = document.createElement("span");
      crown.className = "crown";
      crown.textContent = "  👑";
      title.appendChild(crown);
    }
    const score = document.createElement("div");
    score.className = "score";
    score.textContent = candidate.score == null ? "—" : candidate.score.toFixed(2);
    row.append(title, score);
    card.appendChild(row);

    const sub = document.createElement("div");
    sub.className = "card-sub";
    sub.textContent = candidate.url ? "Tap to inspect in 3D" : "Mesh path captured";
    card.appendChild(sub);

    const metrics = [
      ["Shape", candidate.visual_score],
      ["Look", candidate.appearance_score],
      ["Face", candidate.face_detail_score],
      ["Face worst", candidate.face_detail_min_score],
      ["Detail", candidate.detail_score],
      ["Material", candidate.material_score],
      ["Texture", candidate.texture_resolution_score],
      ["FaceMesh", candidate.head_density_score],
      ["FaceTex", candidate.head_texel_density_score],
      ["FaceDetail", candidate.head_texture_detail_score],
    ].filter(([, value]) => value != null);
    if (metrics.length) {
      const meter = document.createElement("div");
      meter.className = "quality-metrics";
      metrics.forEach(([name, value]) => {
        const item = document.createElement("span");
        item.textContent = `${name} ${Number(value).toFixed(1)}`;
        meter.appendChild(item);
      });
      card.appendChild(meter);
    }
    if (candidate.pbr_channels?.length || candidate.base_color_max_edge) {
      const channels = document.createElement("div");
      channels.className = "pbr-channels";
      const parts = [];
      if (candidate.base_color_min_edge) {
        const strongest = candidate.base_color_max_edge && candidate.base_color_max_edge !== candidate.base_color_min_edge
          ? `–${candidate.base_color_max_edge}px`
          : "";
        parts.push(`baseColor ${candidate.base_color_min_edge}px${strongest}`);
      } else if (candidate.base_color_max_edge) {
        parts.push(`baseColor ${candidate.base_color_max_edge}px`);
      }
      if (candidate.head_region_faces) {
        parts.push(`head ${candidate.head_region_faces.toLocaleString()} tris`);
      }
      if (candidate.head_region_density_ratio != null) {
        parts.push(`head density ${Number(candidate.head_region_density_ratio).toFixed(2)}×`);
      } else if (candidate.head_region_median_edge_normalized != null) {
        parts.push(`head edge ${Number(candidate.head_region_median_edge_normalized).toFixed(5)}× diag`);
      }
      if (candidate.head_texel_density_ratio != null) {
        parts.push(`face texel ${Number(candidate.head_texel_density_ratio).toFixed(2)}× global`);
      }
      if (candidate.head_texture_detail_ratio != null) {
        parts.push(`face detail ${Number(candidate.head_texture_detail_ratio).toFixed(2)}× global`);
      }
      if (candidate.pbr_channels?.length) parts.push(candidate.pbr_channels.join(" · "));
      channels.textContent = "QA · " + parts.join(" · ");
      card.appendChild(channels);
    }
    if (candidate.url) {
      card.addEventListener("click", () => showModel(candidate.url, candidate.label, "Live Arena candidate"));
    }
    list.appendChild(card);
  });
}

function renderJobs(jobs) {
  const list = $("jobs");
  list.replaceChildren();
  if (!jobs.length) {
    const empty = document.createElement("div");
    empty.className = "muted-card";
    empty.textContent = "No jobs in this Studio session.";
    list.appendChild(empty);
    return;
  }
  jobs.slice(0, 10).forEach((job) => {
    const card = document.createElement("div");
    card.className = "job-card";
    card.innerHTML = `<div class="card-row"><div class="card-title">${job.id}</div><div class="score">${job.progress}%</div></div><div class="card-sub">${job.profile} · ${job.stage} · ${job.status}</div>`;
    card.addEventListener("click", () => attachJob(job.id));
    list.appendChild(card);
  });
}

async function refreshJobs() {
  try {
    const res = await fetch("/api/jobs", {cache:"no-store"});
    renderJobs(await res.json());
  } catch (err) {
    appendLog("Studio API error: " + err);
  }
}

async function refreshJob() {
  if (!state.job?.id) return;
  const res = await fetch(`/api/jobs/${state.job.id}`, {cache:"no-store"});
  if (!res.ok) return;
  state.job = await res.json();
  setProgress(state.job.stage, state.job.progress, state.job.status);
  renderCandidates(state.job);
  renderCompositePlan(state.job.composite_plan, state.job.composite_details);
  renderSemanticAnatomy(state.job.semantic_anatomy);
  renderPortablePack(state.job.portable_pack);
  renderAAA(state.job.aaa_acceptance);
  renderFinalQa(state.job.final_qa);
  if (state.job.final_model_url) {
    showModel(state.job.final_model_url, "Final Champion", `${state.job.profile} · ${state.job.portable_target}`);
  }
}

function handleEvent(event) {
  if (event.kind === "log") appendLog(event.line);
  if (event.kind === "stage") setProgress(event.stage, event.progress, event.status);
  if (event.kind === "candidate") refreshJob();
  if (event.kind === "judge_score") {
    appendLog(`Judge #${event.rank}: ${event.label} = ${event.score.toFixed(2)}`);
    refreshJob();
  }
  if (event.kind === "judge_metrics" && event.candidate) {
    const index = state.job?.candidates?.findIndex((x) => x.label === event.label) ?? -1;
    if (index >= 0) {
      state.job.candidates[index] = event.candidate;
      renderCandidates(state.job);
    } else {
      refreshJob();
    }
  }
  if (event.kind === "composite_plan" && event.plan) {
    if (state.job) state.job.composite_plan = event.plan;
    renderCompositePlan(event.plan, state.job?.composite_details || []);
    appendLog("Composite base: " + (event.plan.base_backend || "unknown"));
  }
  if (event.kind === "composite_detail" && event.detail) {
    if (state.job) {
      if (!Array.isArray(state.job.composite_details)) state.job.composite_details = [];
      state.job.composite_details.push(event.detail);
      renderCompositePlan(state.job.composite_plan, state.job.composite_details);
    }
    appendLog(
      "Composite detail: "
      + (event.detail.source || "detail")
      + " · " + (event.detail.strategy || "fusion")
      + (event.detail.accessory_confidence == null
        ? " · seam=" + (event.detail.seam_p95 == null ? "—" : Number(event.detail.seam_p95).toFixed(1))
        : " · match=" + Number(event.detail.accessory_confidence).toFixed(2))
    );
  }
  if (event.kind === "composite_detail_state") {
    if (state.job && Array.isArray(state.job.composite_details)) {
      const item = [...state.job.composite_details].reverse().find(
        (entry) => entry.label === event.label
      );
      if (item) {
        item.status = event.status;
        if (event.reason) item.reason = event.reason;
      }
      renderCompositePlan(state.job.composite_plan, state.job.composite_details);
    }
    appendLog(
      "Composite detail "
      + (event.source || event.label || "detail")
      + ": "
      + (event.status || "updated")
    );
  }
  if (event.kind === "champion") {
    appendLog(`👑 Champion: ${event.label} score=${event.score}`);
    refreshJob();
  }
  if (event.kind === "qa_ready") {
    renderFinalQa(event.qa);
  }
  if (event.kind === "semantic_anatomy" && event.semantic) {
    if (state.job) state.job.semantic_anatomy = event.semantic;
    renderSemanticAnatomy(event.semantic);
    appendLog(
      "Semantic anatomy: "
      + (event.semantic.ready ? "PASS" : "BLOCKED")
    );
  }
  if (event.kind === "portable_pack" && event.pack) {
    if (state.job) state.job.portable_pack = event.pack;
    renderPortablePack(event.pack);
    appendLog(
      "Portable LOD parity: "
      + (event.pack.lod_parity_ready ? "PASS" : "BLOCKED")
    );
  }
  if (event.kind === "aaa_ready" && event.aaa) {
    if (state.job) state.job.aaa_acceptance = event.aaa;
    renderAAA(event.aaa);
    appendLog("AAA gates: " + Number(event.aaa.passed_required || 0) + "/" + Number(event.aaa.total_required || 0));
  }
  if (event.kind === "model" && event.url) {
    showModel(event.url, "Final Champion", "HAYUYA final");
  }
  if (event.kind === "error") toast(event.message || "Job failed");
}

async function attachJob(jobId) {
  if (state.source) state.source.close();
  state.logs = [];
  $("log").textContent = "";
  const res = await fetch(`/api/jobs/${jobId}`, {cache:"no-store"});
  if (!res.ok) return;
  state.job = await res.json();
  setProgress(state.job.stage, state.job.progress, state.job.status);
  renderCandidates(state.job);
  renderCompositePlan(state.job.composite_plan, state.job.composite_details);
  renderSemanticAnatomy(state.job.semantic_anatomy);
  renderPortablePack(state.job.portable_pack);
  renderAAA(state.job.aaa_acceptance);
  renderFinalQa(state.job.final_qa);
  if (state.job.final_model_url) showModel(state.job.final_model_url, "Final Champion");

  const source = new EventSource(`/api/jobs/${jobId}/events`);
  state.source = source;
  source.onmessage = (msg) => {
    try { handleEvent(JSON.parse(msg.data)); } catch {}
  };
  source.onerror = () => {
    if (state.job?.status === "complete" || state.job?.status === "failed") source.close();
  };
  toast("Attached to " + jobId);
}

async function startJob() {
  if (!state.files.length) {
    toast("Choose at least one photo.");
    return;
  }
  const btn = $("runButton");
  btn.disabled = true;
  btn.textContent = "Starting…";

  const body = new FormData();
  state.files.forEach((file) => body.append("images", file, file.name));
  state.faceFiles.forEach((file) => body.append("face_images", file, file.name));
  body.append("profile", $("profile").value);
  body.append("mode", $("mode").value);
  body.append("portable_target", $("tier").value);

  try {
    const res = await fetch("/api/jobs", {method:"POST", body});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not start job");
    await attachJob(data.id);
    await refreshJobs();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate 3D";
  }
}

$("images").addEventListener("change", (e) => setFiles(e.target.files));
$("faceImages").addEventListener("change", (e) => setFaceFiles(e.target.files));
$("runButton").addEventListener("click", startJob);
$("refreshJobs").addEventListener("click", refreshJobs);
$("clearLog").addEventListener("click", () => { state.logs=[]; $("log").textContent=""; });
$("resetView").addEventListener("click", () => {
  const viewer = $("viewer");
  viewer.cameraOrbit = "0deg 75deg auto";
  viewer.cameraTarget = "auto auto auto";
});
$("autoRotate").addEventListener("click", () => {
  const viewer = $("viewer");
  viewer.autoRotate = !viewer.autoRotate;
  $("autoRotate").classList.toggle("active", viewer.autoRotate);
});

$("animationPlay").addEventListener("click", () => {
  const viewer = $("viewer");
  if (!viewer.availableAnimations?.length) return;
  if (viewer.paused) {
    viewer.play();
    $("animationPlay").textContent = "Pause";
  } else {
    viewer.pause();
    $("animationPlay").textContent = "Play";
  }
});

$("animationSelect").addEventListener("change", (e) => {
  const viewer = $("viewer");
  viewer.animationName = e.target.value;
  viewer.currentTime = 0;
  viewer.play();
  $("animationPlay").textContent = "Pause";
});

$("viewer").addEventListener("load", () => {
  syncAnimationControls();
  $("viewerError").hidden = true;
});

$("viewer").addEventListener("error", () => {
  $("viewerError").hidden = false;
  $("animationControls").hidden = true;
  state.currentModelUrl = null;
});

function wireDropzone(element, onFiles) {
  ["dragenter","dragover"].forEach((name) => element.addEventListener(name, (e) => {
    e.preventDefault();
    element.classList.add("drag");
  }));
  ["dragleave","drop"].forEach((name) => element.addEventListener(name, (e) => {
    e.preventDefault();
    element.classList.remove("drag");
  }));
  element.addEventListener("drop", (e) => onFiles(e.dataTransfer.files));
}

wireDropzone($("dropzone"), setFiles);
wireDropzone($("faceDropzone"), setFaceFiles);

(async () => {
  try {
    const info = await (await fetch("/api/info")).json();
    $("serverStatus").textContent = info.mobile_ready ? "LAN READY" : "LOCAL";
  } catch {
    $("serverStatus").textContent = "OFFLINE";
    $("serverStatus").classList.remove("online");
  }
  refreshJobs();
  setInterval(() => {
    refreshJobs();
    if (state.job?.id) refreshJob();
  }, 3500);
})();