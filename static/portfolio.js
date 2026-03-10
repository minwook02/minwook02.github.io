function formatSignedPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatValue(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function toneClass(changePercent) {
  if (changePercent > 0.15) {
    return "up";
  }
  if (changePercent < -0.15) {
    return "down";
  }
  return "flat";
}

function applyPreview(cardId, valueId, changeId, cards, decimals = 2) {
  const card = cards.find((item) => item.id === cardId);
  if (!card) {
    return;
  }

  document.getElementById(valueId).textContent = formatValue(card.price, decimals);
  const changeNode = document.getElementById(changeId);
  changeNode.textContent = formatSignedPercent(card.changePercent);
  changeNode.className = `preview-change ${toneClass(card.changePercent)}`;
}

async function loadPortfolioPreview() {
  try {
    const response = await fetch("./data/dashboard.json?t=" + Date.now(), {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const cards = payload.cards || [];
    document.getElementById("marketUpdatedAt").textContent =
      payload.updatedLabel || "업데이트 정보 없음";

    applyPreview("kospi", "previewKospi", "previewKospiChange", cards, 2);
    applyPreview("nasdaq", "previewNasdaq", "previewNasdaqChange", cards, 2);
    applyPreview("usdkrw", "previewUsdkrw", "previewUsdkrwChange", cards, 2);

    const signal = payload.summary?.signal;
    const signalNode = document.getElementById("previewSignal");
    signalNode.textContent = signal?.label || "Mixed";
    signalNode.className = `signal-pill ${signal?.tone || "neutral"}`;
    document.getElementById("previewSignalMessage").textContent =
      signal?.message || "시장 신호 데이터를 불러오지 못했습니다.";
  } catch (error) {
    document.getElementById("marketUpdatedAt").textContent = "연결 실패";
    document.getElementById("previewSignal").textContent = "Unavailable";
    document.getElementById("previewSignalMessage").textContent =
      "시장 데이터 프리뷰를 불러오지 못했습니다.";
  }
}

loadPortfolioPreview();
