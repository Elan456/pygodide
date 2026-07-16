const status = document.getElementById({{ status_element_id | tojson }});
const canvas = document.getElementById({{ canvas_element_id | tojson }});

const pyodidePackages = {{ pyodide_packages | tojson }};
const micropipPackages = {{ micropip_packages | tojson }};
const declaredPackageNames = {{ declared_package_names | tojson }};
const packageFiles = {{ package_files | tojson }};
const assetBasePath = {{ asset_base_path | tojson }};
const virtualFsRoot = {{ virtual_fs_root | tojson }};
const startupPythonCode = {{ startup_python_code | tojson }};
const readyLogMessage = {{ ready_log | tojson }};
const canvasLayout = {{ canvas_layout | tojson }};
const canvasAspectWidth = {{ canvas_width | tojson }};
const canvasAspectHeight = {{ canvas_height | tojson }};
const pygodideVersion = {{ pygodide_version | tojson }};
// Build-time fingerprint of packaged files. Same content → same URL → browser
// cache can reuse assets across reloads. Rebuild after edits to pick up changes.
const assetRequestCacheBuster = {{ asset_cache_buster | tojson }};
// Cap concurrent asset fetches (browser HTTP/1.1 limits are often ~6 per origin).
const ASSET_FETCH_CONCURRENCY = 8;
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
  loadingAppHint: {{ loading_app_hint_text | tojson }},
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

// Progress fractions for each boot stage (0–1).
const LOADING_PROGRESS = {
  startingPyodide: 0.14,
  loadingPackages: 0.4,
  loadingMicropip: 0.55,
  loadingFiles: 0.72,
  loadingApp: 0.9,
  complete: 1,
};

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

function setStatus(message, state = "active", { progress = null } = {}) {
  if (status) {
    status.textContent = message;
    status.dataset.state = state;
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

function getLoadingAppStatusMessage() {
  return `${statusText.loadingApp} ${statusText.loadingAppHint}`.trim();
}

function getSyncEntrypointHelpMessage() {
  return [
    "Your game entrypoint is synchronous and is blocking the browser.",
    "",
    "The page cannot update, paint, or open a right-click menu while a tight",
    "while-loop runs without yielding.",
    "",
    "Fix (pick one):",
    "  1. Rebuild WITHOUT --no-auto-async so pygodide can convert simple loops, or",
    "  2. Make the entry async and yield each frame:",
    "       async def main():",
    "           while running:",
    "               ...",
    "               await asyncio.sleep(1 / (60 * 2))",
    "",
    "Docs: https://elan456.github.io/pygodide/instructions/#make-the-game-async-compatible",
  ].join("\n");
}

function getAsyncHangHelpMessage() {
  // Stable prefix for smoke manifests (smoke.expected-warning) and log grepping.
  return [
    "[pygodide] async hang: your async entrypoint never yielded control.",
    "",
    "The browser main thread is blocked, so the page cannot update or paint.",
    "You may have forgotten await asyncio.sleep(...) in your game loop, or the",
    "app got stuck in a tight loop or long blocking call.",
    "",
    "Fix: yield every frame inside the loop, for example:",
    "  async def main():",
    "      while running:",
    "          ...",
    "          await asyncio.sleep(1 / (60 * 2))",
    "",
    "Docs: https://elan456.github.io/pygodide/instructions/#make-the-game-async-compatible",
  ].join("\n");
}

let appReadyMarked = false;

function markAppReady() {
  if (appReadyMarked) {
    return Promise.resolve();
  }
  appReadyMarked = true;
  console.info(readyLogMessage);
  return hideLoadingUi();
}

function allowLoaderTextSelection() {
  const loader = document.getElementById("pygodide-loader");
  if (loader) {
    // Allow selecting/copying help text before (or if) the thread freezes.
    loader.style.pointerEvents = "auto";
  }
}

function warnSyncEntrypoint() {
  // Keep the loading chrome visible with actionable text. Sync infinite loops
  // freeze the main thread next; this message must already be on screen.
  console.warn(getSyncEntrypointHelpMessage());
  setStatus(getSyncEntrypointHelpMessage(), "error");
  allowLoaderTextSelection();
}

function warnAsyncHang() {
  // Must run before await entrypoint(). If the coroutine never awaits, JS timers
  // cannot fire — so this guidance has to be painted first (like sync freeze).
  // Healthy games clear it via markAppReady() after their first yield.
  console.warn(getAsyncHangHelpMessage());
  setStatus(getAsyncHangHelpMessage(), "error");
  allowLoaderTextSelection();
}

// Called from generated Python startup (js.pygodideMarkAppReady / Warn...).
globalThis.pygodideMarkAppReady = markAppReady;
globalThis.pygodideWarnSyncEntrypoint = warnSyncEntrypoint;
globalThis.pygodideWarnAsyncHang = warnAsyncHang;

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

function formatAssetFetchError(filename, url, detail) {
  const cleanUrl = String(url).replace(/([?&])_pygodide=[^&]*/g, "$1").replace(/[?&]$/, "");
  return [
    `Failed to download staged file '${filename}'.`,
    `URL: ${cleanUrl}`,
    detail,
    "",
    "The build listed this path for the browser, but the web host did not serve it.",
    "Common causes:",
    "- Deploy omitted the file (GitHub Pages upload-pages-artifact always excludes .git and .github)",
    "- Auto-discovery included a tooling path that is not part of the game",
    "- The published build/ is incomplete or from an older deploy",
    "",
    "Fix: rebuild with a current pygodide (tooling dirs are skipped), or set",
    "[tool.pygodide].include to only the files your game needs, then redeploy build/.",
  ].join("\n");
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

function joinVirtualPath(root, relativePath) {
  const normalizedRoot = root.startsWith("/") ? root : `/${root}`;
  const trimmedRoot = normalizedRoot.replace(/\/+$/, "");
  const trimmedPath = relativePath.replace(/^\/+/, "");
  return `${trimmedRoot}/${trimmedPath}`;
}

function ensureParentDir(runtime, filePath) {
  const lastSlash = filePath.lastIndexOf("/");
  if (lastSlash <= 0) {
    return;
  }
  runtime.FS.mkdirTree(filePath.slice(0, lastSlash));
}

function resolveAssetUrl(filename) {
  const url = new URL(filename, new URL(assetBasePath, import.meta.url));
  url.searchParams.set("_pygodide", assetRequestCacheBuster);
  return url.toString();
}

async function fetchAssetBytes(filename) {
  const url = resolveAssetUrl(filename);
  let response;
  try {
    // Default HTTP cache: content-hashed `_pygodide` query changes when the
    // package set changes, so stale assets are not kept after a rebuild.
    response = await fetch(url);
  } catch (error) {
    const detail =
      error instanceof Error ? `Network error: ${error.message}` : `Network error: ${error}`;
    throw new Error(formatAssetFetchError(filename, url, detail), { cause: error });
  }
  if (!response.ok) {
    throw new Error(
      formatAssetFetchError(
        filename,
        url,
        `HTTP ${response.status} ${response.statusText || ""}`.trim(),
      ),
    );
  }
  return new Uint8Array(await response.arrayBuffer());
}

async function stageAppFiles(runtime) {
  const total = packageFiles.length;
  if (total === 0) {
    return;
  }

  const progressStart = LOADING_PROGRESS.loadingFiles;
  const progressEnd = LOADING_PROGRESS.loadingApp;
  let completed = 0;
  let nextIndex = 0;

  function reportProgress(filename) {
    const fraction =
      total <= 1
        ? progressEnd
        : progressStart + ((progressEnd - progressStart) * completed) / total;
    setStatus(
      `${statusText.loadingFiles} (${completed}/${total})\n${filename}`,
      "active",
      { progress: fraction },
    );
  }

  // Show the first file immediately so the loading bar does not stay idle.
  reportProgress(packageFiles[0]);
  await waitForNextPaint();

  async function stageOne(filename) {
    try {
      const source = await fetchAssetBytes(filename);
      const targetPath = joinVirtualPath(virtualFsRoot, filename);
      ensureParentDir(runtime, targetPath);
      runtime.FS.writeFile(targetPath, source);
    } catch (error) {
      if (error instanceof Error && error.message.includes("Failed to download staged file")) {
        throw error;
      }
      throw new Error(
        `Failed while staging '${filename}' into the browser filesystem.\n${errorToString(error)}`,
        { cause: error },
      );
    }
    completed += 1;
    reportProgress(filename);
  }

  async function worker() {
    while (nextIndex < total) {
      const index = nextIndex;
      nextIndex += 1;
      await stageOne(packageFiles[index]);
    }
  }

  const workerCount = Math.min(ASSET_FETCH_CONCURRENCY, total);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
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

  console.warn(getLoadingAppStatusMessage());
  setStatus(getLoadingAppStatusMessage(), "active", {
    progress: LOADING_PROGRESS.loadingApp,
  });
  await waitForNextPaint();

  // Do not hide the loader before the entrypoint runs. Async games arm hang
  // guidance first, then hide via pygodideMarkAppReady() after the first yield.
  // Sync game loops keep the loader up with pygodideWarnSyncEntrypoint() instead
  // of an empty frozen canvas (and a page that cannot open DevTools via right-click).
  await runtime.runPythonAsync(startupPythonCode);
}

boot().catch((error) => {
  console.error(error);
  setStatus(formatPyodideError(error), "error");
});
