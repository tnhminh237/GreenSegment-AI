export const SECTORS = ['agriculture', 'energy', 'industry', 'international', 'residential', 'transport', 'waste'];
export const SECTOR_LABELS = {
  agriculture: 'Nông nghiệp', energy: 'Năng lượng', industry: 'Công nghiệp',
  international: 'Quốc tế', residential: 'Dân cư', transport: 'Giao thông', waste: 'Chất thải',
};
export const SECTOR_COLORS = {
  agriculture: '#6bbf63', energy: '#5097e8', industry: '#f4a261', international: '#bb91e6',
  residential: '#e9bf62', transport: '#ef7390', waste: '#adb5c1',
};
export const CLUSTER_COLORS = { 0: '#3b82f6', 1: '#f59e0b', 2: '#10b981' };
export const shortClusterName = { 0: 'Dân cư · Giao thông', 1: 'Công nghiệp', 2: 'Năng lượng' };
export const num = (v, digits = 0) => Number(v ?? 0).toLocaleString('vi-VN', {
  minimumFractionDigits: digits, maximumFractionDigits: digits,
});
export const pct = (v, digits = 1) => `${num(v, digits)}%`;
export const ghg = (v) => num(v, 0);
export function topSectors(shares, n = 3) {
  return [...SECTORS].sort((a, b) => (shares?.[b] ?? 0) - (shares?.[a] ?? 0)).slice(0, n);
}
