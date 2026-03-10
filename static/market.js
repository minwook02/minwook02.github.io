function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }

  return new Intl.NumberFormat("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function formatSigned(value, decimals = 2, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }

  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, decimals)}${suffix}`;
}

function toneClass(tone) {
  if (tone === "up") {
    return "tone-up";
  }
  if (tone === "down") {
    return "tone-down";
  }
  return "tone-flat";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function buildSparkline(points, height = 72) {
  if (!points || points.length < 2) {
    return `<svg class="sparkline" viewBox="0 0 100 ${height}" preserveAspectRatio="none"></svg>`;
  }

  const values = points.map((point) => point[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 1e-9);
  const width = 100;

  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((point[1] - min) / spread) * (height - 8) - 4;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  const gradientId = `gradient-${Math.random().toString(36).slice(2, 8)}`;
  const last = points[points.length - 1][1];
  const first = points[0][1];
  const tone = last >= first ? "up" : "down";
  const stroke = tone === "up" ? "#d94a38" : "#1f63d8";
  const fill = tone === "up" ? "rgba(217, 74, 56, 0.12)" : "rgba(31, 99, 216, 0.12)";

  return `
    <svg class="sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="${gradientId}" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="${fill.replace("0.12", "0.28")}" />
          <stop offset="100%" stop-color="${fill.replace("0.12", "0.02")}" />
        </linearGradient>
      </defs>
      <path d="${path} L ${width} ${height} L 0 ${height} Z" fill="url(#${gradientId})"></path>
      <path d="${path}" fill="none" stroke="${stroke}" stroke-width="2.5" stroke-linecap="round"></path>
    </svg>
  `;
}

function buildLargeChart(points) {
  return buildSparkline(points, 160).replace('class="sparkline"', 'class="chart-svg"');
}

function renderSummary(summary) {
  document.getElementById("signalLabel").textContent = summary.signal.label;
  document.getElementById("signalMessage").textContent = summary.signal.message;

  const signalTone = document.getElementById("signalTone");
  signalTone.className = `signal-chip ${summary.signal.tone || "neutral"}`;
  signalTone.textContent =
    summary.signal.tone === "up"
      ? "위험 선호"
      : summary.signal.tone === "down"
        ? "방어 우세"
        : "혼조";

  const overviewList = document.getElementById("overviewList");
  overviewList.innerHTML = summary.overview
    .map((item) => `<div class="overview-item">${escapeHtml(item)}</div>`)
    .join("");

  const checkpointList = document.getElementById("checkpointList");
  checkpointList.innerHTML = summary.checkpoints
    .map((item) => `<span class="checkpoint">${escapeHtml(item)}</span>`)
    .join("");
}

function renderMainCharts(charts) {
  const container = document.getElementById("mainCharts");
  container.innerHTML = charts
    .map(
      (chart) => `
        <article class="chart-card">
          <div class="chart-meta">
            <div>
              <p class="label">${escapeHtml(chart.group)}</p>
              <h3>${escapeHtml(chart.label)}</h3>
            </div>
            <span class="signal-chip ${chart.tone}">${escapeHtml(chart.direction)}</span>
          </div>
          <div class="chart-price">${formatNumber(chart.price, chart.decimals)}</div>
          <div class="chart-change ${toneClass(chart.tone)}">
            ${formatSigned(chart.change, chart.decimals)} / ${formatSigned(chart.changePercent, 2, "%")}
          </div>
          ${buildLargeChart(chart.series)}
          <div class="chart-asof">${escapeHtml(chart.marketTime || "시간 정보 없음")}</div>
        </article>
      `,
    )
    .join("");
}

function groupCards(cards, groups) {
  return groups
    .map((group) => ({
      title: group,
      cards: cards.filter((card) => card.group === group),
    }))
    .filter((group) => group.cards.length);
}

function renderCards(cards, groups) {
  const container = document.getElementById("cardGroups");
  container.innerHTML = groupCards(cards, groups)
    .map(
      (group) => `
        <section>
          <div class="group-title">
            <p class="label">${escapeHtml(group.title)}</p>
          </div>
          <div class="asset-grid">
            ${group.cards
              .map(
                (card) => `
                  <article class="asset-card">
                    <div class="asset-head">
                      <div>
                        <h3>${escapeHtml(card.label)}</h3>
                        <div class="asset-symbol">${escapeHtml(card.symbol)}</div>
                      </div>
                      <span class="signal-chip ${card.tone}">${escapeHtml(card.direction)}</span>
                    </div>
                    <div class="asset-price">${formatNumber(card.price, card.decimals)}</div>
                    <div class="asset-change ${toneClass(card.tone)}">
                      ${formatSigned(card.change, card.decimals)} / ${formatSigned(card.changePercent, 2, "%")}
                    </div>
                    ${buildSparkline(card.series)}
                    <div class="asset-asof">${escapeHtml(card.marketTime || "시간 정보 없음")}</div>
                  </article>
                `,
              )
              .join("")}
          </div>
        </section>
      `,
    )
    .join("");
}

function renderMovers(summary) {
  document.getElementById("leadersList").innerHTML = summary.leaders
    .map(
      (item) => `
        <div class="mover-item">
          <div class="mover-name">${escapeHtml(item.label)}</div>
          <div class="${toneClass("up")}">${formatSigned(item.changePercent, 2, "%")}</div>
        </div>
      `,
    )
    .join("");

  document.getElementById("laggardsList").innerHTML = summary.laggards
    .map(
      (item) => `
        <div class="mover-item">
          <div class="mover-name">${escapeHtml(item.label)}</div>
          <div class="${toneClass("down")}">${formatSigned(item.changePercent, 2, "%")}</div>
        </div>
      `,
    )
    .join("");
}

function renderHeadlines(headlines) {
  const container = document.getElementById("headlines");
  if (!headlines.length) {
    container.innerHTML = `<div class="headline-item"><div class="headline-title">불러온 헤드라인이 없습니다.</div></div>`;
    return;
  }

  container.innerHTML = headlines
    .map(
      (headline) => `
        <article class="headline-item">
          <a class="headline-link" href="${escapeHtml(headline.link || "#")}" target="_blank" rel="noreferrer">
            <div class="headline-title">${escapeHtml(headline.title || "제목 없음")}</div>
            <div class="headline-meta">
              ${escapeHtml(headline.source || "출처 미상")}
              ${headline.publishedAt ? ` · ${escapeHtml(headline.publishedAt)}` : ""}
            </div>
          </a>
        </article>
      `,
    )
    .join("");
}

function renderErrors(errors) {
  const panel = document.getElementById("errorPanel");
  const list = document.getElementById("errorList");

  if (!errors.length) {
    panel.classList.add("hidden");
    list.innerHTML = "";
    return;
  }

  panel.classList.remove("hidden");
  list.innerHTML = errors
    .map((item) => `<div class="error-item">${escapeHtml(item)}</div>`)
    .join("");
}

async function loadDashboard(force = false) {
  const refreshButton = document.getElementById("refreshButton");
  const dataUrl = document.body.dataset.dataUrl || "../data/dashboard.json";
  refreshButton.disabled = true;
  refreshButton.textContent = "불러오는 중";

  try {
    const query = force ? `?t=${Date.now()}` : "";
    const response = await fetch(`${dataUrl}${query}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    document.getElementById("updatedAt").textContent = data.updatedLabel;
    renderSummary(data.summary);
    renderMainCharts(data.mainCharts);
    renderCards(data.cards, data.groups);
    renderMovers(data.summary);
    renderHeadlines(data.headlines);
    renderErrors(data.errors);
  } catch (error) {
    document.getElementById("signalLabel").textContent = "데이터 오류";
    document.getElementById("signalMessage").textContent =
      "시세 또는 뉴스 데이터를 불러오지 못했습니다. 잠시 후 다시 시도하세요.";
    renderErrors([error.message]);
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = "새로고침";
  }
}

document.getElementById("refreshButton").addEventListener("click", () => {
  loadDashboard(true);
});

loadDashboard();
window.setInterval(() => loadDashboard(true), 180000);
