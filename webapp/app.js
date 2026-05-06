const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// ── Config sent from bot via initData or hardcoded for demo ──────────────────
const CONFIG = {
  cardNumber: "8600 1234 5678 9012",
  cardHolder: "AZIZ KARIMOV",
  bankName: "Uzcard",
  payAmount: 50000,
  timerSeconds: 300,   // 5 minutes
};

// ── State ────────────────────────────────────────────────────────────────────
let timerInterval = null;
let timerRemaining = 0;
let timerTotal = CONFIG.timerSeconds;
let paymentActive = false;

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Apply Telegram theme
  document.documentElement.style.setProperty("--bg",  tg.themeParams.bg_color || "#0f0f13");
  document.documentElement.style.setProperty("--bg2", tg.themeParams.secondary_bg_color || "#1a1a22");
  document.documentElement.style.setProperty("--text",tg.themeParams.text_color || "#ffffff");
  document.documentElement.style.setProperty("--hint",tg.themeParams.hint_color || "#8e8e9e");

  loadUser();
  renderCardInfo();
  setupMainButton();
});

// ── User Info ────────────────────────────────────────────────────────────────
function loadUser() {
  const user = tg.initDataUnsafe?.user;
  if (user) {
    document.getElementById("userName").textContent =
      [user.first_name, user.last_name].filter(Boolean).join(" ");
    document.getElementById("userId").textContent = `ID: ${user.id}`;
    const initials = (user.first_name?.[0] || "U").toUpperCase();
    document.getElementById("userAvatar").textContent = initials;
  }
  // Demo balance — in production, fetch from your backend
  document.getElementById("balanceAmount").textContent = "0 so'm";
}

// ── Card Info ─────────────────────────────────────────────────────────────────
function renderCardInfo() {
  document.getElementById("cardNumber").textContent = CONFIG.cardNumber;
  document.getElementById("cardHolder").textContent  = CONFIG.cardHolder;
  document.getElementById("bankName").textContent    = CONFIG.bankName;
  document.getElementById("payAmount").textContent   =
    CONFIG.payAmount.toLocaleString("uz-UZ") + " so'm";
}

// ── Main Button ───────────────────────────────────────────────────────────────
function setupMainButton() {
  tg.MainButton.setText("💳 To'lovni boshlash");
  tg.MainButton.color = "#6c63ff";
  tg.MainButton.show();
  tg.MainButton.onClick(startPayment);
}

// ── Copy Card ─────────────────────────────────────────────────────────────────
function copyCard() {
  const raw = CONFIG.cardNumber.replace(/\s/g, "");
  if (navigator.clipboard) {
    navigator.clipboard.writeText(raw).then(() => showToast("✅ Karta raqami nusxalandi!"));
  } else {
    // Fallback
    const el = document.createElement("textarea");
    el.value = raw;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
    showToast("✅ Karta raqami nusxalandi!");
  }
}

// ── Start Payment ─────────────────────────────────────────────────────────────
function startPayment() {
  if (paymentActive) {
    showToast("⏳ To'lov allaqachon boshlangan!");
    return;
  }

  paymentActive = true;
  timerRemaining = CONFIG.timerSeconds;
  timerTotal = CONFIG.timerSeconds;

  document.getElementById("payBtn").style.display = "none";
  document.getElementById("confirmBtn").style.display = "flex";
  document.getElementById("timerBlock").style.display = "block";

  tg.MainButton.setText("✅ To'lovni tasdiqlash");
  tg.MainButton.color = "#22c55e";
  tg.MainButton.offClick(startPayment);
  tg.MainButton.onClick(confirmPayment);

  tg.HapticFeedback?.impactOccurred("medium");
  showToast("⏱ 5 daqiqa vaqtingiz bor!");

  runTimer();
}

// ── Timer ────────────────────────────────────────────────────────────────────
function runTimer() {
  updateTimerUI(timerRemaining);

  timerInterval = setInterval(() => {
    timerRemaining--;
    updateTimerUI(timerRemaining);

    if (timerRemaining <= 0) {
      clearInterval(timerInterval);
      onTimerExpired();
    }
  }, 1000);
}

function updateTimerUI(remaining) {
  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;
  const display = document.getElementById("timerDisplay");
  const bar = document.getElementById("timerBar");

  display.textContent = `${String(mins).padStart(2,"0")}:${String(secs).padStart(2,"0")}`;

  const pct = (remaining / timerTotal) * 100;
  bar.style.width = pct + "%";

  // Color states
  display.classList.remove("warning","danger");
  bar.classList.remove("warning","danger");

  if (remaining <= 60) {
    display.classList.add("danger");
    bar.classList.add("danger");
  } else if (remaining <= 120) {
    display.classList.add("warning");
    bar.classList.add("warning");
  }
}

function onTimerExpired() {
  paymentActive = false;
  document.getElementById("timerDisplay").textContent = "00:00";
  document.getElementById("confirmBtn").style.display = "none";
  document.getElementById("payBtn").style.display = "flex";

  tg.MainButton.setText("💳 To'lovni boshlash");
  tg.MainButton.color = "#6c63ff";
  tg.MainButton.offClick(confirmPayment);
  tg.MainButton.onClick(startPayment);

  tg.HapticFeedback?.notificationOccurred("error");
  showToast("⌛ Vaqt tugadi! Qaytadan bosing.");
}

// ── Confirm Payment ───────────────────────────────────────────────────────────
function confirmPayment() {
  if (!paymentActive) return;

  clearInterval(timerInterval);
  paymentActive = false;

  document.getElementById("confirmBtn").disabled = true;
  tg.MainButton.disable();
  tg.MainButton.showProgress(true);

  tg.HapticFeedback?.notificationOccurred("success");

  // Send data to bot
  tg.sendData(JSON.stringify({
    action: "payment_confirmed",
    amount: CONFIG.payAmount,
    timestamp: Date.now(),
  }));

  document.getElementById("timerBlock").style.display = "none";
  document.getElementById("confirmBtn").style.display = "none";
  document.getElementById("payBtn").style.display = "flex";

  showToast("✅ So'rovingiz adminga yuborildi!");

  // Add to local history
  addHistoryItem({
    status: "pending",
    amount: CONFIG.payAmount,
    date: new Date().toLocaleString("uz-UZ"),
  });

  tg.MainButton.hideProgress();
  tg.MainButton.offClick(confirmPayment);
  tg.MainButton.onClick(startPayment);
  tg.MainButton.setText("💳 To'lovni boshlash");
  tg.MainButton.color = "#6c63ff";
  tg.MainButton.enable();

  setTimeout(() => tg.close(), 2000);
}

// ── History ──────────────────────────────────────────────────────────────────
const statusConfig = {
  approved: { icon: "✅", label: "Tasdiqlandi", cls: "approved" },
  pending:  { icon: "⏳", label: "Kutilmoqda",  cls: "pending"  },
  rejected: { icon: "❌", label: "Rad etildi",  cls: "rejected" },
  expired:  { icon: "⌛", label: "Muddati o'tdi", cls: "expired" },
};

function addHistoryItem({ status, amount, date }) {
  const list = document.getElementById("historyList");
  const empty = list.querySelector(".history-empty");
  if (empty) empty.remove();

  const cfg = statusConfig[status] || statusConfig.pending;
  const item = document.createElement("div");
  item.className = "history-item";
  item.innerHTML = `
    <div class="history-icon ${cfg.cls}">${cfg.icon}</div>
    <div class="history-info">
      <div class="history-title">${cfg.label}</div>
      <div class="history-date">${date}</div>
    </div>
    <div class="history-amount ${cfg.cls}">+${amount.toLocaleString()} so'm</div>
  `;
  list.prepend(item);
}

// ── Toast ────────────────────────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}
