// CPU and RAM charts, fed by /api/metrics every few seconds.

import { t } from '../i18n.js';

const MAX_POINTS = 60;
const POLL_MS = 3000;

let cpuChart = null;
let ramChart = null;

// Chart colors come from the design tokens in static/css/base.css.
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function makeChartData(color) {
  return {
    labels: Array(MAX_POINTS).fill(''),
    datasets: [{
      data: Array(MAX_POINTS).fill(null),
      borderColor: color,
      backgroundColor: color + '1f',
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.4,
    }]
  };
}

const chartOpts = (max) => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
  scales: {
    x: { display: false },
    y: {
      display: true,
      min: 0, max: max,
      grid: { color: cssVar('--chart-grid'), drawBorder: false },
      ticks: {
        color: cssVar('--chart-ticks'), font: { size: 10, family: cssVar('--font-sans') }, maxTicksLimit: 3,
        callback: v => v + '%'
      }
    }
  }
});

function pushChart(chart, value) {
  chart.data.datasets[0].data.push(value);
  if (chart.data.datasets[0].data.length > MAX_POINTS)
    chart.data.datasets[0].data.shift();
  chart.update('none');
}

async function fetchMetrics() {
  try {
    const r = await fetch('/api/metrics');
    if (r.status === 401) { window.location.href = '/login'; return; }
    const d = await r.json();

    const ramPct = d.ram_total > 0 ? Math.round(d.ram_used / d.ram_total * 100) : 0;

    document.getElementById('cpu-val').textContent = (d.cpu ?? 0).toFixed(1) + '%';
    document.getElementById('ram-val').textContent = ramPct + '%';
    document.getElementById('proc-cpu-sub').textContent =
      t('metrics.process_cpu', { value: d.running ? (d.cpu ?? 0).toFixed(1) + '%' : '—%' });
    document.getElementById('proc-ram-sub').textContent = d.running
      ? t('metrics.process_ram', { used: d.ram_process ?? 0, total: d.ram_total })
      : t('metrics.process_ram_idle');

    pushChart(cpuChart, d.cpu ?? 0);
    pushChart(ramChart, ramPct);
  } catch (e) {}
}

export function initMetrics() {
  cpuChart = new Chart(document.getElementById('chart-cpu'), {
    type: 'line',
    data: makeChartData(cssVar('--cpu-color')),
    options: chartOpts(100)
  });

  ramChart = new Chart(document.getElementById('chart-ram'), {
    type: 'line',
    data: makeChartData(cssVar('--ram-color')),
    options: chartOpts(100)
  });

  setInterval(fetchMetrics, POLL_MS);
  fetchMetrics();
}
