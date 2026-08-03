const status = document.getElementById({{ status_element_id | tojson }});
const canvas = document.getElementById({{ canvas_element_id | tojson }});

const pyodidePackages = {{ pyodide_packages | tojson }};
const micropipPackages = {{ micropip_packages | tojson }};
const declaredPackageNames = {{ declared_package_names | tojson }};
// Single compressed archive of game code + assets (build-time app.zip).
const appArchivePath = {{ app_archive_path | tojson }};
const assetBasePath = {{ asset_base_path | tojson }};
const virtualFsRoot = {{ virtual_fs_root | tojson }};
const startupPythonCode = {{ startup_python_code | tojson }};
const readyLogMessage = {{ ready_log | tojson }};
const canvasLayout = {{ canvas_layout | tojson }};
const canvasAspectWidth = {{ canvas_width | tojson }};
const canvasAspectHeight = {{ canvas_height | tojson }};
const pygodideVersion = {{ pygodide_version | tojson }};
// Build-time fingerprint of the app archive. Same content → same URL → browser
// cache can reuse the zip across reloads. Rebuild after edits to pick up changes.
const assetRequestCacheBuster = {{ asset_cache_buster | tojson }};
const knownImportPackageAliases = {
  pygame: "pygame-ce",
};
// Keep in sync with .pygodide-shell padding (20px each side).
const CANVAS_VIEWPORT_PADDING = 40;
const statusText = {
  startingPyodide: {{ starting_pyodide_status_text | tojson }},
  loadingPackages: {{ loading_packages_status_text | tojson }},
  loadingFiles: {{ loading_files_status_text | tojson }},
  loadingApp: {{ loading_app_status_text | tojson }},
  running: {{ running_status_text | tojson }},
};

function requireElement(element, id) {
  if (!element) {
    throw new Error(`Missing required element: #${id}`);
  }
  return element;
}

// Keep in sync with #pygodide-loader opacity transition in index.html.
const LOADING_UI_FADE_MS = 180;
// Soft hang re-detect after the game has become ready (main thread still runs).
const HANG_TIMEOUT_MS = 2000;
const HANG_POLL_MS = 250;

// Progress fractions for each boot stage (0–1).
const LOADING_PROGRESS = {
  startingPyodide: 0.14,
  loadingPackages: 0.4,
  loadingMicropip: 0.55,
  loadingFiles: 0.72,
  loadingApp: 0.9,
  complete: 1,
};

function setCanvasPointerEventsForChrome(state) {
  // While error text is shown, block the canvas so wheel/drag on the status
  // scrollport cannot fall through to SDL/canvas under the loader.
  if (!canvas) {
    return;
  }
  if (state === "error") {
    canvas.style.pointerEvents = "none";
  } else if (canvas.style.pointerEvents === "none") {
    canvas.style.pointerEvents = "";
  }
}

function setLoadingChromeState(state) {
  // Visible while loading or on error; hidden before the game starts drawing.
  const chromeState =
    state === "hidden" ? "hidden" : state === "error" ? "error" : "active";
  const loader = document.getElementById("pygodide-loader");
  if (loader) {
    loader.dataset.state = chromeState;
  }
  const version = document.getElementById("pygodide-version");
  if (version) {
    // Version badge follows loading visibility, not error chrome.
    version.dataset.state = state === "hidden" ? "hidden" : "active";
  }
  const progress = document.getElementById("pygodide-progress");
  if (progress && state === "hidden") {
    progress.dataset.state = "hidden";
  }
  setCanvasPointerEventsForChrome(chromeState);
}

function snakeGridMetrics(track) {
  const styles = getComputedStyle(track);
  const cell = Number.parseFloat(styles.getPropertyValue("--cell")) || 12;
  const seg = Number.parseFloat(styles.getPropertyValue("--seg")) || 10;
  const padX = Number.parseFloat(styles.getPropertyValue("--pad-x")) || 6;
  const contentWidth = Math.max(0, track.clientWidth - padX * 2);
  // At least 2 cells: one for the snake, one for the apple.
  const totalCells = Math.max(2, Math.floor(contentWidth / cell));
  return { cell, seg, padX, totalCells };
}

function layoutSnakeProgress(track, fill, fraction, { error = false } = {}) {
  const { cell, totalCells } = snakeGridMetrics(track);
  // Last cell is reserved for the apple; snake grows through the rest.
  const maxSnakeCells = Math.max(1, totalCells - 1);
  const filledCells = error
    ? maxSnakeCells
    : Math.max(1, Math.min(maxSnakeCells, Math.round(fraction * maxSnakeCells)));

  // Exact multiples of --cell so segments stay on the grid (no mid-cell widths).
  fill.style.width = `${filledCells * cell}px`;
  // Head (and eyes) sit in the last filled cell interior.
  fill.style.setProperty("--head-left", `${(filledCells - 1) * cell}px`);
  // Apple in the last full playfield cell.
  track.style.setProperty("--apple-inset", `${(totalCells - 1) * cell}px`);
}

function setProgress(fraction, { error = false } = {}) {
  const clamped = Math.max(0, Math.min(1, fraction));
  const fill = document.getElementById("pygodide-progress-fill");
  const track = document.getElementById("pygodide-progress");
  if (fill && track) {
    layoutSnakeProgress(track, fill, clamped, { error });
  }
  if (track) {
    track.dataset.state = error ? "error" : "active";
    track.setAttribute("aria-valuenow", String(Math.round(clamped * 100)));
  }
}

function setStatus(
  message,
  state = "active",
  { progress = null, wide = false } = {},
) {
  if (status) {
    status.textContent = message;
    status.dataset.state = state;
    if (wide) {
      status.dataset.wide = "true";
    } else {
      delete status.dataset.wide;
    }
  }
  if (state === "error") {
    setProgress(1, { error: true });
  } else if (typeof progress === "number") {
    setProgress(progress);
  }
  setLoadingChromeState(state);
}

function hideLoadingUi() {
  setProgress(LOADING_PROGRESS.complete);
  setStatus("", "hidden");
  const loader = document.getElementById("pygodide-loader");
  if (!loader) {
    return Promise.resolve();
  }

  // Ensure the browser applies the "active" styles before transitioning out.
  void loader.offsetWidth;

  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) {
        return;
      }
      settled = true;
      loader.removeEventListener("transitionend", onEnd);
      resolve();
    };
    const onEnd = (event) => {
      if (event.target === loader && event.propertyName === "opacity") {
        finish();
      }
    };
    loader.addEventListener("transitionend", onEnd);
    window.setTimeout(finish, LOADING_UI_FADE_MS + 80);
  });
}

function getHangHelpMessage() {
  // Keep in sync with ASYNC_HANG_WARNING_MARKER in rendering.py (smoke
  // expected-warning matches a stable substring of this text).
  // Keep this short: pre-paint runs on every launch (including healthy games
  // that take a moment before the first yield), so word it as "if stuck" not
  // a definite hang. Long text also jumps the logo/progress bar.
  return (
    "If you stay stuck here, the game is not yielding. " +
    "Add `await asyncio.sleep(1 / (fps * 2))` once per frame in your main loop."
  );
}

let appReadyMarked = false;
let watchdogArmed = false;
let hangVisible = false;
let lastHeartbeatAt = 0;

function allowLoaderTextSelection() {
  const loader = document.getElementById("pygodide-loader");
  if (loader) {
    // Allow selecting/copying help text before (or if) the thread freezes.
    loader.style.pointerEvents = "auto";
  }
}

function showHangHelp() {
  // Use normal loader text (not error/red). Never-yield freezes must already
  // have this on screen (timers cannot paint after a hard freeze). Healthy
  // games clear it via markAppReady after the first yield. Wider status so
  // the short hang line fits without clipping at the fixed height.
  const message = getHangHelpMessage();
  hangVisible = true;
  console.warn(message);
  setStatus(message, "active", { wide: true });
  allowLoaderTextSelection();
}

function armWatchdog() {
  // Paint hang guidance *before* the entrypoint may hard-freeze the thread.
  // JS timers cannot open a new message after a tight loop starts, so this
  // pre-paint is required for never-yield freezes (e.g. async_hang). Healthy
  // games clear it via markAppReady() after the first yield; heartbeats keep
  // a soft timer reset. Soft stalls after ready re-show via the interval.
  watchdogArmed = true;
  hangVisible = false;
  lastHeartbeatAt = Date.now();
  showHangHelp();
}

function heartbeatWatchdog() {
  lastHeartbeatAt = Date.now();
  if (appReadyMarked && hangVisible) {
    // Soft-stall recovery: hide hang chrome while the game keeps running.
    hangVisible = false;
    setStatus("", "hidden");
  }
}

function disarmWatchdog() {
  watchdogArmed = false;
  hangVisible = false;
}

function markAppReady() {
  if (appReadyMarked) {
    return Promise.resolve();
  }
  appReadyMarked = true;
  hangVisible = false;
  lastHeartbeatAt = Date.now();
  console.info(readyLogMessage);
  return hideLoadingUi();
}

// After ready, re-show hang if heartbeats stop but the main thread still runs
// (soft stalls). Hard freezes at startup rely on pre-paint in armWatchdog().
window.setInterval(() => {
  if (!watchdogArmed || !appReadyMarked || hangVisible) {
    return;
  }
  if (Date.now() - lastHeartbeatAt >= HANG_TIMEOUT_MS) {
    showHangHelp();
  }
}, HANG_POLL_MS);

// Called from generated Python startup (js.pygodideMarkAppReady / Arm / Heartbeat).
globalThis.pygodideMarkAppReady = markAppReady;
globalThis.pygodideWatchdogArm = armWatchdog;
globalThis.pygodideHeartbeat = heartbeatWatchdog;
globalThis.pygodideWatchdogDisarm = disarmWatchdog;

function normalizePackageName(name) {
  return name.toLowerCase().replace(/_/g, "-");
}

function extractPythonErrorText(error) {
  if (!error || typeof error.message !== "string") {
    return null;
  }

  const message = error.message.trim();
  if (!message) {
    return null;
  }

  if (message.includes("Traceback")) {
    return message;
  }

  if (error.name === "PythonError") {
    return message;
  }

  return null;
}

function errorToString(error) {
  const pythonError = extractPythonErrorText(error);
  if (pythonError) {
    return pythonError;
  }

  if (error instanceof Error) {
    const message = (error.message || error.name || "Unknown error").trim();
    const stack = typeof error.stack === "string" ? error.stack.trim() : "";
    // Safari/Firefox often put only frames in `.stack`, without the message.
    if (stack && message && !stack.includes(message)) {
      return `${message}\n\n${stack}`;
    }
    if (stack) {
      return stack;
    }
    return message;
  }

  return String(error);
}

function extractMissingModuleName(errorText) {
  const match = errorText.match(/ModuleNotFoundError:\s+No module named ['"]([^'"]+)['"]/);
  if (!match) {
    return null;
  }
  return match[1].split(".")[0];
}

function guessPackageNameForModule(moduleName) {
  if (moduleName in knownImportPackageAliases) {
    return knownImportPackageAliases[moduleName];
  }

  const normalizedModuleName = normalizePackageName(moduleName);
  const configuredPackage = declaredPackageNames.find((packageName) => {
    return normalizePackageName(packageName) === normalizedModuleName;
  });
  if (configuredPackage) {
    return configuredPackage;
  }

  return normalizedModuleName;
}

function formatConfiguredDependencies() {
  if (declaredPackageNames.length === 0) {
    return "(none)";
  }
  return declaredPackageNames.join(", ");
}

function formatArchiveFetchError(url, detail) {
  const cleanUrl = String(url).replace(/([?&])_pygodide=[^&]*/g, "$1").replace(/[?&]$/, "");
  return [
    `Failed to download the game archive '${appArchivePath}'.`,
    `URL: ${cleanUrl}`,
    detail,
    "",
    "The build expects this zip next to index.html, but the web host did not serve it.",
    "Common causes:",
    "- Deploy omitted app.zip (incomplete build/ upload)",
    "- The published build/ is from an older pygodide that used per-file staging",
    "",
    "Fix: rebuild with a current pygodide and redeploy the full build/ folder",
    "(index.html, boot.js, app.zip, and shell assets).",
  ].join("\n");
}

function formatBytes(byteCount) {
  if (!Number.isFinite(byteCount) || byteCount < 0) {
    return "?";
  }
  if (byteCount < 1024) {
    return `${byteCount} B`;
  }
  if (byteCount < 1024 * 1024) {
    return `${(byteCount / 1024).toFixed(1)} KB`;
  }
  return `${(byteCount / (1024 * 1024)).toFixed(1)} MB`;
}

/** Map download ratio into the files→app progress band (0–1 overall). */
function mapDownloadProgress(received, total, progressStart, progressEnd) {
  if (!(total > 0) || !Number.isFinite(received)) {
    return null;
  }
  const ratio = Math.max(0, Math.min(1, received / total));
  return progressStart + (progressEnd - progressStart) * ratio;
}

function formatPyodideError(error) {
  const errorText = errorToString(error);
  const missingModuleName = extractMissingModuleName(errorText);
  if (!missingModuleName) {
    return `Error:\n${errorText}`;
  }

  const suggestedPackageName = guessPackageNameForModule(missingModuleName);
  const normalizedSuggestedPackageName = normalizePackageName(suggestedPackageName);
  const isConfigured = declaredPackageNames.some((packageName) => {
    return normalizePackageName(packageName) === normalizedSuggestedPackageName;
  });

  const guidance = [
    `Pygodide could not import Python module '${missingModuleName}'.`,
  ];

  if (suggestedPackageName !== missingModuleName) {
    guidance.push(
      `This import usually comes from package '${suggestedPackageName}'.`
    );
  }

  if (isConfigured) {
    guidance.push(
      `This build declared '${suggestedPackageName}', but the import still failed.`
    );
    guidance.push(
      "Check that the package is available for Pyodide and that the import name matches the installed package."
    );
  } else {
    guidance.push(
      `This build did not declare a dependency that provides '${missingModuleName}'.`
    );
    guidance.push(
      `Add '${suggestedPackageName}' to [project].dependencies in your pyproject.toml, then rebuild.`
    );
  }

  guidance.push(`Configured dependencies for this build: ${formatConfiguredDependencies()}`);
  guidance.push("");
  guidance.push("Underlying Pyodide error:");
  guidance.push(errorText);

  return guidance.join("\n");
}

function waitForNextPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

function viewportMaxSize() {
  return {
    width: Math.max(1, Math.floor(window.innerWidth - CANVAS_VIEWPORT_PADDING)),
    height: Math.max(1, Math.floor(window.innerHeight - CANVAS_VIEWPORT_PADDING)),
  };
}

function applyCanvasBufferSize(canvasEl, width, height) {
  canvasEl.width = width;
  canvasEl.height = height;
  canvasEl.style.width = `${width}px`;
  canvasEl.style.height = `${height}px`;
}

function sizeCanvasToViewport(canvasEl) {
  // Stretch to the full usable viewport (may change aspect ratio).
  const { width, height } = viewportMaxSize();
  applyCanvasBufferSize(canvasEl, width, height);
}

function sizeCanvasToFitAspect(canvasEl, aspectWidth, aspectHeight) {
  // Largest integer size that fits the viewport while keeping the game ratio.
  const { width: maxWidth, height: maxHeight } = viewportMaxSize();
  const safeAspectWidth = Math.max(1, aspectWidth);
  const safeAspectHeight = Math.max(1, aspectHeight);
  const scale = Math.min(maxWidth / safeAspectWidth, maxHeight / safeAspectHeight);
  const width = Math.max(1, Math.floor(safeAspectWidth * scale));
  const height = Math.max(1, Math.floor(safeAspectHeight * scale));
  applyCanvasBufferSize(canvasEl, width, height);
}

function applyCanvasLayout(canvasEl) {
  if (canvasLayout === "fill") {
    sizeCanvasToViewport(canvasEl);
    return;
  }
  if (canvasLayout === "fit") {
    sizeCanvasToFitAspect(canvasEl, canvasAspectWidth, canvasAspectHeight);
  }
  // "fixed" keeps the HTML width/height attributes from index.html.
}

function resolveArchiveUrl() {
  const url = new URL(appArchivePath, new URL(assetBasePath, import.meta.url));
  // Default HTTP cache: content-hashed `_pygodide` changes when the archive
  // changes, so a refresh reuses the zip and rebuilds pick up new content.
  url.searchParams.set("_pygodide", assetRequestCacheBuster);
  return url.toString();
}

async function fetchAppArchiveBytes(onProgress) {
  const url = resolveArchiveUrl();
  let response;
  try {
    response = await fetch(url);
  } catch (error) {
    const detail =
      error instanceof Error ? `Network error: ${error.message}` : `Network error: ${error}`;
    throw new Error(formatArchiveFetchError(url, detail), { cause: error });
  }
  if (!response.ok) {
    throw new Error(
      formatArchiveFetchError(
        url,
        `HTTP ${response.status} ${response.statusText || ""}`.trim(),
      ),
    );
  }

  const totalHeader = response.headers.get("Content-Length");
  const total = totalHeader ? Number(totalHeader) : NaN;
  const knownTotal = Number.isFinite(total) && total > 0;

  // Prefer streaming so we can advance the bar from bytes received.
  if (response.body && typeof response.body.getReader === "function") {
    const reader = response.body.getReader();
    const chunks = [];
    let received = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      chunks.push(value);
      received += value.byteLength;
      if (typeof onProgress === "function") {
        onProgress(received, knownTotal ? total : null);
      }
    }
    const merged = new Uint8Array(received);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return merged;
  }

  const buffer = new Uint8Array(await response.arrayBuffer());
  if (typeof onProgress === "function") {
    onProgress(buffer.byteLength, knownTotal ? total : buffer.byteLength);
  }
  return buffer;
}

async function stageAppFiles(runtime) {
  const progressStart = LOADING_PROGRESS.loadingFiles;
  const progressEnd = LOADING_PROGRESS.loadingApp;

  function reportDownloadProgress(received, total) {
    const mapped = mapDownloadProgress(received, total, progressStart, progressEnd);
    if (mapped !== null && total != null) {
      setStatus(
        `${statusText.loadingFiles} (${formatBytes(received)} / ${formatBytes(total)})`,
        "active",
        { progress: mapped },
      );
      return;
    }
    // No Content-Length: keep a clear status and a fixed mid-band progress so
    // the bar does not look stuck at 0 or jump randomly.
    setStatus(
      `${statusText.loadingFiles}\n${formatBytes(received)} received`,
      "active",
      { progress: progressStart + (progressEnd - progressStart) * 0.35 },
    );
  }

  setStatus(statusText.loadingFiles, "active", { progress: progressStart });
  await waitForNextPaint();

  let archiveBytes;
  try {
    archiveBytes = await fetchAppArchiveBytes(reportDownloadProgress);
  } catch (error) {
    if (error instanceof Error && error.message.includes("Failed to download the game archive")) {
      throw error;
    }
    throw new Error(
      `Failed while downloading '${appArchivePath}'.\n${errorToString(error)}`,
      { cause: error },
    );
  }

  setStatus(`${statusText.loadingFiles}\nUnpacking...`, "active", {
    progress: progressEnd,
  });
  await waitForNextPaint();

  try {
    // Same relative paths as the project (main.py, assets/...), under virtualFsRoot.
    runtime.unpackArchive(archiveBytes, "zip", { extractDir: virtualFsRoot });
  } catch (error) {
    throw new Error(
      `Failed while unpacking '${appArchivePath}' into the browser filesystem.\n${errorToString(error)}`,
      { cause: error },
    );
  }
}

async function boot() {
  const requiredCanvas = requireElement(canvas, {{ canvas_element_id | tojson }});
  requireElement(status, {{ status_element_id | tojson }});

  applyCanvasLayout(requiredCanvas);
  if (canvasLayout === "fit" || canvasLayout === "fill") {
    window.addEventListener("resize", () => applyCanvasLayout(requiredCanvas));
  }

  console.info(`pygodide ${pygodideVersion}`);
  setStatus(statusText.startingPyodide, "active", {
    progress: LOADING_PROGRESS.startingPyodide,
  });

  const runtime = await loadPyodide();
  runtime._api._skip_unwind_fatal_error = true;

  runtime.canvas.setCanvas2D(requiredCanvas);

  if (pyodidePackages.length > 0) {
    setStatus(statusText.loadingPackages, "active", {
      progress: LOADING_PROGRESS.loadingPackages,
    });
    await runtime.loadPackage(pyodidePackages);
  }

  if (micropipPackages.length > 0) {
    setStatus(statusText.loadingPackages, "active", {
      progress: LOADING_PROGRESS.loadingMicropip,
    });
    await runtime.loadPackage("micropip");
    const micropip = runtime.pyimport("micropip");
    await micropip.install(micropipPackages);
  }

  await stageAppFiles(runtime);

  setStatus(statusText.loadingApp, "active", {
    progress: LOADING_PROGRESS.loadingApp,
  });
  await waitForNextPaint();

  // Do not hide the loader before the entrypoint runs. Startup arms the yield
  // watchdog (paints hang help once for never-yield freezes), then hides via
  // pygodideMarkAppReady() after the first yield (or when a short-lived
  // entrypoint returns).
  await runtime.runPythonAsync(startupPythonCode);
}

boot().catch((error) => {
  console.error(error);
  disarmWatchdog();
  setStatus(formatPyodideError(error), "error");
});
