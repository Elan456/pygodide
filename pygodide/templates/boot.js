const status = document.getElementById({{ status_element_id | tojson }});
const canvas = document.getElementById({{ canvas_element_id | tojson }});

const pyodidePackages = {{ pyodide_packages | tojson }};
const micropipPackages = {{ micropip_packages | tojson }};
const pythonFiles = {{ python_files | tojson }};
const assetBasePath = {{ asset_base_path | tojson }};
const virtualFsRoot = {{ virtual_fs_root | tojson }};
const startupPythonCode = {{ startup_python_code | tojson }};
const assetRequestCacheBuster = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
const statusText = {
  startingPyodide: {{ starting_pyodide_status_text | tojson }},
  loadingPackages: {{ loading_packages_status_text | tojson }},
  stagingFiles: {{ staging_files_status_text | tojson }},
  loadingApp: {{ loading_app_status_text | tojson }},
  running: {{ running_status_text | tojson }},
};

function requireElement(element, id) {
  if (!element) {
    throw new Error(`Missing required element: #${id}`);
  }
  return element;
}

function setStatus(message) {
  if (status) {
    status.textContent = message;
  }
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

async function fetchTextFile(filename) {
  const response = await fetch(resolveAssetUrl(filename), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${filename}: ${response.status} ${response.statusText}`);
  }
  return await response.text();
}

async function stagePythonFiles(runtime) {
  for (const filename of pythonFiles) {
    const source = await fetchTextFile(filename);
    const targetPath = joinVirtualPath(virtualFsRoot, filename);
    ensureParentDir(runtime, targetPath);
    runtime.FS.writeFile(targetPath, source, { encoding: "utf8" });
  }
}

async function boot() {
  const requiredCanvas = requireElement(canvas, {{ canvas_element_id | tojson }});
  requireElement(status, {{ status_element_id | tojson }});

  setStatus(statusText.startingPyodide);

  const runtime = await loadPyodide();
  runtime._api._skip_unwind_fatal_error = true;

  runtime.canvas.setCanvas2D(requiredCanvas);

  if (pyodidePackages.length > 0) {
    setStatus(statusText.loadingPackages);
    await runtime.loadPackage(pyodidePackages);
  }

  if (micropipPackages.length > 0) {
    await runtime.loadPackage("micropip");
    const micropip = runtime.pyimport("micropip");
    await micropip.install(micropipPackages);
  }

  setStatus(statusText.stagingFiles);
  await stagePythonFiles(runtime);

  setStatus(statusText.loadingApp);
  await runtime.runPythonAsync(startupPythonCode);

  setStatus(statusText.running);
}

boot().catch((error) => {
  console.error(error);
  setStatus(`Error: ${error}`);
});
