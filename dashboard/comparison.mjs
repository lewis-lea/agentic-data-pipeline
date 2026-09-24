/** Pure comparison logic shared by the chart and Node's built-in tests. */
export function validDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}

export function prepareSeries(item, { normalise, base, start, end, mode = 'price' }) {
  normalise = normalise || mode === 'total';
  if (![start, end].every(validDate) || start > end) {
    return { error: 'Choose a valid chart date range.' };
  }
  if (normalise && !validDate(base)) return { error: 'Choose a valid reference date.' };
  const source = mode === 'total' ? item.adjusted_points : item.points;
  if (!source?.length) return { error: mode === 'total' ? 'Adjusted history unavailable; total return cannot be calculated.' : 'No price history available.' };
  const points = source.filter(([d, p]) => validDate(d) && Number.isFinite(p) && p > 0)
    .sort((a, b) => a[0].localeCompare(b[0]));
  if (!points.length) return { error: 'No price history available.' };
  let reference = null;
  if (normalise) {
    if (base > points.at(-1)[0]) return { error: 'Reference date is after the last observation.' };
    reference = points.findLast(([date]) => date <= base);
    if (!reference) return { error: 'No price on or before the reference date.' };
    // Accommodate weekends/holidays, but never silently use a long-stale baseline.
    if ((Date.parse(base) - Date.parse(reference[0])) / 86400000 > 7) {
      return { error: 'No reference price within the preceding seven days.' };
    }
  }
  const visible = points.filter(([date]) => date >= start && date <= end)
    .map(([date, price]) => [date, normalise ? 100 * price / reference[1] : price]);
  if (!visible.length) return { error: 'No observations in the selected chart range.' };
  return { ...item, points: visible, reference, unit: normalise ? 'Index' : item.currency };
}

export function extent(values) {
  const low = values.reduce((a, b) => Math.min(a, b), Infinity);
  const high = values.reduce((a, b) => Math.max(a, b), -Infinity);
  const pad = (high - low || Math.abs(high) || 1) * 0.06;
  return [low - pad, high + pad];
}

export function nearestPoint(points, day) {
  let lo = 0, hi = points.length - 1;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (Date.parse(points[mid][0]) <= day) lo = mid;
    else hi = mid - 1;
  }
  return points[lo];
}
