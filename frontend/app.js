const BASE_URL = "http://localhost:8001/api/v1";

// Application State
const state = {
  token: localStorage.getItem("token") || null,
  user: null,
  selectedFile: null,
  documents: []
};

// DOM Elements
const navItems = document.querySelectorAll(".nav-item");
const viewPanes = document.querySelectorAll(".view-pane");
const pageTitle = document.getElementById("page-title");
const sidebarUserStatus = document.getElementById("sidebar-user-status");
const userProfileHeader = document.getElementById("user-profile-header");
const headerAvatar = document.getElementById("header-avatar");
const headerUsername = document.getElementById("header-username");
const logoutBtn = document.getElementById("logout-btn");

// Auth Form Elements
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const formLogin = document.getElementById("form-login");
const formRegister = document.getElementById("form-register");

// Document elements
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const uploadStatusWrapper = document.getElementById("upload-status-wrapper");
const uploadFilename = document.getElementById("upload-filename");
const uploadPercent = document.getElementById("upload-percent");
const uploadProgressFill = document.getElementById("upload-progress-fill");
const uploadBtn = document.getElementById("upload-btn");
const documentList = document.getElementById("document-list");

// Search elements
const queryInput = document.getElementById("query-input");
const queryBtn = document.getElementById("query-btn");
const searchTypeSelect = document.getElementById("search-type");
const searchLimitInput = document.getElementById("search-limit");
const searchRerankCheckbox = document.getElementById("search-rerank");
const answerOutputWrapper = document.getElementById("answer-output-wrapper");
const answerBody = document.getElementById("answer-body");
const citationsList = document.getElementById("citations-list");

// Evaluation elements
const evalRetrievalJson = document.getElementById("eval-retrieval-json");
const runRetrievalEvalBtn = document.getElementById("run-retrieval-eval-btn");
const retrievalEvalResults = document.getElementById("retrieval-eval-results");
const valHitRate = document.getElementById("val-hit-rate");
const valMrr = document.getElementById("val-mrr");

const evalGenQuery = document.getElementById("eval-gen-query");
const evalGenContext = document.getElementById("eval-gen-context");
const evalGenAnswer = document.getElementById("eval-gen-answer");
const runGenEvalBtn = document.getElementById("run-gen-eval-btn");
const genEvalResults = document.getElementById("gen-eval-results");
const valFaithfulness = document.getElementById("val-faithfulness");
const valRelevance = document.getElementById("val-relevance");

// --- Initialization & UI Routing ---
function init() {
  setupNavigation();
  setupAuthTabs();
  setupAuthForms();
  setupIngestion();
  setupSearch();
  setupEvaluation();

  if (state.token) {
    checkAuthentication();
  } else {
    lockNavigation();
    showPane("auth");
  }
}

function setupNavigation() {
  navItems.forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      if (item.classList.contains("locked")) return;

      const targetView = item.getAttribute("href").substring(1);
      showPane(targetView);
    });
  });

  logoutBtn.addEventListener("click", logout);
}

function showPane(viewId) {
  navItems.forEach(item => {
    if (item.getAttribute("href") === `#${viewId}`) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  viewPanes.forEach(pane => {
    if (pane.id === `view-${viewId}`) {
      pane.classList.add("active");
    } else {
      pane.classList.remove("active");
    }
  });

  // Set Page Title
  const titles = {
    auth: "Authentication Console",
    documents: "Workspace Document Manager",
    search: "Semantic Knowledge Search",
    evaluation: "RAG Evaluation Metrics"
  };
  pageTitle.textContent = titles[viewId] || "Enterprise AI Platform";
}

function lockNavigation() {
  navItems.forEach(item => {
    if (item.id !== "nav-auth") {
      item.classList.add("locked");
    }
  });
}

function unlockNavigation() {
  navItems.forEach(item => {
    item.classList.remove("locked");
  });
}

// --- Toast Notifications ---
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === "success" ? "✓" : "✗"}</span> <span>${message}</span>`;
  
  container.appendChild(toast);

  // Auto remove
  setTimeout(() => {
    toast.classList.add("fade-out");
    toast.addEventListener("animationend", () => {
      toast.remove();
    });
  }, 4000);
}

// --- Authentication Handler ---
async function checkAuthentication() {
  try {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });

    if (res.status === 200) {
      const data = await res.json();
      state.user = data;
      updateUserUI(true);
      unlockNavigation();
      showPane("documents");
      fetchDocuments();
    } else {
      // Invalid/Expired token
      logout();
    }
  } catch (err) {
    showToast("Server connection failed.", "error");
    logout();
  }
}

function updateUserUI(isAuthenticated) {
  if (isAuthenticated && state.user) {
    // Header profile
    userProfileHeader.style.display = "flex";
    headerUsername.textContent = state.user.full_name;
    headerAvatar.textContent = state.user.full_name.charAt(0).toUpperCase();

    // Sidebar status
    sidebarUserStatus.innerHTML = `
      <span class="status-dot online"></span>
      <span class="status-text">Connected: ${state.user.email}</span>
    `;
  } else {
    userProfileHeader.style.display = "none";
    sidebarUserStatus.innerHTML = `
      <span class="status-dot offline"></span>
      <span class="status-text">Not Authenticated</span>
    `;
  }
}

function setupAuthTabs() {
  tabLogin.addEventListener("click", () => {
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    formLogin.classList.add("active");
    formRegister.classList.remove("active");
  });

  tabRegister.addEventListener("click", () => {
    tabRegister.classList.add("active");
    tabLogin.classList.remove("active");
    formRegister.classList.add("active");
    formLogin.classList.remove("active");
  });
}

function setupAuthForms() {
  // Login Submit
  formLogin.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;

    try {
      const res = await fetch(`${BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });

      const data = await res.json();

      if (res.ok) {
        state.token = data.access_token;
        localStorage.setItem("token", state.token);
        showToast("Login successful!");
        checkAuthentication();
      } else {
        showToast(data.detail || "Authentication failed", "error");
      }
    } catch (err) {
      showToast("Authentication server unavailable.", "error");
    }
  });

  // Register Submit
  formRegister.addEventListener("submit", async (e) => {
    e.preventDefault();
    const full_name = document.getElementById("reg-name").value;
    const email = document.getElementById("reg-email").value;
    const password = document.getElementById("reg-password").value;

    try {
      const res = await fetch(`${BASE_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name })
      });

      const data = await res.json();

      if (res.ok) {
        showToast("Registration successful! Please login.");
        tabLogin.click();
        formLogin.reset();
        formRegister.reset();
      } else {
        showToast(data.detail || "Registration failed", "error");
      }
    } catch (err) {
      showToast("Server unavailable.", "error");
    }
  });
}

function logout() {
  state.token = null;
  state.user = null;
  state.documents = [];
  localStorage.removeItem("token");
  updateUserUI(false);
  lockNavigation();
  showPane("auth");
  formLogin.reset();
  formRegister.reset();
  showToast("Logged out successfully.");
}

// --- Ingestion Handlers ---
function setupIngestion() {
  dropzone.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  uploadBtn.addEventListener("click", uploadFile);
}

function handleFileSelected(file) {
  state.selectedFile = file;
  uploadFilename.textContent = file.name;
  uploadStatusWrapper.style.display = "block";
  uploadPercent.textContent = "0%";
  uploadProgressFill.style.width = "0%";
  uploadBtn.removeAttribute("disabled");
}

async function uploadFile() {
  if (!state.selectedFile) return;

  const formData = new FormData();
  formData.append("file", state.selectedFile);

  uploadBtn.setAttribute("disabled", "true");
  
  // Progress bar simulation (FastAPI background ingestion runs async)
  let progress = 0;
  const timer = setInterval(() => {
    if (progress < 85) {
      progress += 5;
      uploadPercent.textContent = `${progress}%`;
      uploadProgressFill.style.width = `${progress}%`;
    }
  }, 100);

  try {
    const res = await fetch(`${BASE_URL}/documents/upload`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${state.token}`
      },
      body: formData
    });

    clearInterval(timer);
    
    if (res.ok) {
      const data = await res.json();
      uploadPercent.textContent = "100%";
      uploadProgressFill.style.width = "100%";
      showToast("Document ingestion started successfully.");
      
      // Clear selection
      state.selectedFile = null;
      setTimeout(() => {
        uploadStatusWrapper.style.display = "none";
      }, 1500);

      // Refresh file list after delay (to allow backend parser to finish)
      setTimeout(fetchDocuments, 2000);
    } else {
      const errData = await res.json();
      showToast(errData.detail || "Upload failed", "error");
      uploadBtn.removeAttribute("disabled");
    }
  } catch (err) {
    clearInterval(timer);
    showToast("Network upload error.", "error");
    uploadBtn.removeAttribute("disabled");
  }
}

async function fetchDocuments() {
  try {
    const res = await fetch(`${BASE_URL}/documents`, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });

    if (res.ok) {
      state.documents = await res.json();
      renderDocumentList();
    }
  } catch (err) {
    console.error("Failed to load documents list", err);
  }
}

function renderDocumentList() {
  if (state.documents.length === 0) {
    documentList.innerHTML = '<div class="empty-state">No documents uploaded yet</div>';
    return;
  }

  documentList.innerHTML = state.documents.map(doc => {
    const createdStr = new Date(doc.created_at).toLocaleString();
    return `
      <div class="doc-item">
        <div class="doc-info">
          <div class="doc-name" title="${doc.filename}">${doc.filename}</div>
          <div class="doc-meta">ID: ${doc.id} | Uploaded: ${createdStr}</div>
        </div>
        <span class="doc-status processed">Ingested</span>
      </div>
    `;
  }).join("");
}

// --- Search Q&A Handlers ---
function setupSearch() {
  queryBtn.addEventListener("click", runQuerySearch);
  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runQuerySearch();
  });
}

async function runQuerySearch() {
  const query = queryInput.value.trim();
  if (!query) return;

  queryBtn.setAttribute("disabled", "true");
  answerOutputWrapper.style.display = "block";
  answerBody.textContent = "Querying Knowledge Base...";
  citationsList.innerHTML = "";

  const limit = parseInt(searchLimitInput.value, 10);
  const searchType = searchTypeSelect.value;
  const rerank = searchRerankCheckbox.checked;

  try {
    // If the search type is "hybrid" or "keyword" or "vector", and rerank/citations is needed,
    // we can either call Q&A citations POST endpoint, or standard GET search endpoint!
    // Since this is Q&A with citations, we call POST /retrieval/query:
    const res = await fetch(`${BASE_URL}/retrieval/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({ query })
    });

    if (res.ok) {
      const data = await res.json();
      answerBody.textContent = data.answer;
      
      // Render sources
      if (data.sources && data.sources.length > 0) {
        citationsList.innerHTML = data.sources.map((src, idx) => `
          <div class="citation-card">
            <div class="citation-source">[${idx}] Document: ${src.filename} (Chunk #${src.chunk_index})</div>
            <div class="citation-text">"${src.text}"</div>
          </div>
        `).join("");
      } else {
        citationsList.innerHTML = '<div class="citation-text">No references cited in the answer.</div>';
      }
    } else {
      const err = await res.json();
      answerBody.textContent = `Error: ${err.detail || "Query execution failed."}`;
    }
  } catch (err) {
    answerBody.textContent = "Failed to connect to search service.";
  } finally {
    queryBtn.removeAttribute("disabled");
  }
}

// --- Evaluation Handlers ---
function setupEvaluation() {
  runRetrievalEvalBtn.addEventListener("click", runRetrievalEval);
  runGenEvalBtn.addEventListener("click", runGenEval);
}

async function runRetrievalEval() {
  const jsonText = evalRetrievalJson.value.trim();
  let dataset;

  try {
    dataset = JSON.parse(jsonText);
  } catch (e) {
    showToast("Invalid JSON syntax in test dataset", "error");
    return;
  }

  runRetrievalEvalBtn.setAttribute("disabled", "true");
  retrievalEvalResults.style.display = "none";

  try {
    const res = await fetch(`${BASE_URL}/retrieval/evaluate/retrieval`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({ dataset, limit: 5 })
    });

    if (res.ok) {
      const data = await res.json();
      valHitRate.textContent = `${(data.hit_rate * 100).toFixed(1)}%`;
      valMrr.textContent = data.mrr.toFixed(2);
      retrievalEvalResults.style.display = "grid";
      showToast("Retrieval evaluation completed.");
    } else {
      const err = await res.json();
      showToast(err.detail || "Evaluation failed", "error");
    }
  } catch (e) {
    showToast("Failed to run evaluation server call.", "error");
  } finally {
    runRetrievalEvalBtn.removeAttribute("disabled");
  }
}

async function runGenEval() {
  const query = evalGenQuery.value.trim();
  const contextText = evalGenContext.value.trim();
  const answer = evalGenAnswer.value.trim();

  if (!query || !contextText || !answer) {
    showToast("Please fill in all generation evaluation fields", "error");
    return;
  }

  runGenEvalBtn.setAttribute("disabled", "true");
  genEvalResults.style.display = "none";

  try {
    const res = await fetch(`${BASE_URL}/retrieval/evaluate/generation`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({
        query,
        contexts: [contextText],
        answer
      })
    });

    if (res.ok) {
      const data = await res.json();
      valFaithfulness.textContent = `${(data.faithfulness * 100).toFixed(0)}%`;
      valRelevance.textContent = `${(data.relevance * 100).toFixed(0)}%`;
      genEvalResults.style.display = "grid";
      showToast("Generation evaluation completed.");
    } else {
      const err = await res.json();
      showToast(err.detail || "Generation evaluation failed", "error");
    }
  } catch (e) {
    showToast("Failed to run generation evaluation server call.", "error");
  } finally {
    runGenEvalBtn.removeAttribute("disabled");
  }
}

// Start app
window.addEventListener("DOMContentLoaded", init);
