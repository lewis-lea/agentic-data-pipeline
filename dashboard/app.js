const state = {
  data: null,
  selected: new Set(),
};

function nearestPoint(series, isoDate, key) {
  if (!isoDate) return series[0]?.[key] ?? null;
  const target = new Date(`${isoDate}T00:00:00Z`).getTime();
  let best = null;
  for (const point of series) {
    const stamp = new Date(`${point.date}T00:00:00Z`).getTime();
    if (stamp >= target) {
      best = point[key];
      break;
    }
  }
  return best ?? series.at(-1)?.[key] ?? null;
}

function renderList() {
  const root = document.getElementById("instrument-list");
  const query = document.getElementById("search").value.trim().toLowerCase();
  root.replaceChildren();

  for (const instrument of state.data.instruments) {
    const haystack = `${instrument.name} ${instrument.symbol} ${instrument.category}`.toLowerCase();
    if (query && !haystack.includes(query)) continue;

    const label = document.createElement("label");
    label.className = "instrument-row";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selected.has(instrument.symbol);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selected.add(instrument.symbol);
      else state.selected.delete(instrument.symbol);
      renderChart();
    });

    const text = document.createElement("span");
    text.innerHTML = `${instrument.name}<small>${instrument.symbol} · ${instrument.category}</small>`;
    label.append(checkbox, text);
    root.append(label);
  }
}

function renderChart() {
  const mode = document.getElementById("return-mode").value;
  const normalise = document.getElementById("normalise").checked;
  const normaliseDate = document.getElementById("normalise-date").value;

  const traces = [];
  for (const instrument of state.data.instruments) {
    if (!state.selected.has(instrument.symbol)) continue;

    const key = mode === "total" ? "total_return_index" : "price";
    let denominator = 1;
    if (normalise) {
      denominator = nearestPoint(instrument.series, normaliseDate, key);
      if (!denominator) continue;
    }

    traces.push({
      x: instrument.series.map((point) => point.date),
      y: instrument.series.map((point) => normalise ? point[key] / denominator * 100 : point[key]),
      name: `${instrument.name} (${instrument.symbol})`,
      type: "scatter",
      mode: "lines",
      hovertemplate: normalise ? "%{x}<br>%{y:.2f}<extra>%{fullData.name}</extra>" : "%{x}<br>%{y:.4g}<extra>%{fullData.name}</extra>",
    });
  }

  Plotly.react("chart", traces, {
    margin: { l: 62, r: 24, t: 30, b: 52 },
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    hovermode: "x unified",
    legend: { orientation: "h", y: -0.18 },
    xaxis: { title: "Date", rangeslider: { visible: true } },
    yaxis: { title: normalise ? "Normalised value (100 = selected date)" : mode === "total" ? "Total return index" : "Price" },
  }, { responsive: true, displaylogo: false });

  const unresolved = state.data.source?.unresolved?.length ?? 0;
  document.getElementById("status").textContent =
    `${traces.length} series shown. ${state.data.source?.resolved_count ?? state.data.instruments.length} Dodl instruments resolved to Yahoo Finance; ${unresolved} unresolved. Total return assumes cash distributions are reinvested at the aligned closing price.`;
}

async function init() {
  const response = await fetch("data/market.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load dashboard data (${response.status})`);
  state.data = await response.json();

  const initial = state.data.instruments.slice(0, 6);
  for (const instrument of initial) state.selected.add(instrument.symbol);

  const dates = state.data.instruments.flatMap((instrument) => instrument.series.map((point) => point.date));
  dates.sort();
  if (dates.length) {
    document.getElementById("normalise-date").value = dates[Math.floor(dates.length * 0.2)];
  }

  document.getElementById("updated").textContent =
    `Data generated ${new Date(state.data.generated_at).toLocaleString()}`;

  document.getElementById("search").addEventListener("input", renderList);
  for (const id of ["return-mode", "normalise", "normalise-date"]) {
    document.getElementById(id).addEventListener("change", renderChart);
  }
  document.getElementById("select-all").addEventListener("click", () => {
    state.selected = new Set(state.data.instruments.map((instrument) => instrument.symbol));
    renderList();
    renderChart();
  });
  document.getElementById("select-none").addEventListener("click", () => {
    state.selected.clear();
    renderList();
    renderChart();
  });

  renderList();
  renderChart();
}

init().catch((error) => {
  document.getElementById("status").textContent = error.message;
  console.error(error);
});
