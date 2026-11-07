import React from 'react';
import { BarChart3, Globe2, Info, Layers3, Leaf, Search, SlidersHorizontal, Sparkles, X } from 'lucide-react';
import { SECTORS, SECTOR_LABELS } from '../constants.js';

const TABS = [
  { id: 'overview', label: 'Tổng quan', Icon: BarChart3 },
  { id: 'clusters', label: 'Cluster Explorer', Icon: Layers3 },
  { id: 'city', label: 'Tra cứu đô thị', Icon: Search },
  { id: 'advisor', label: 'Giải pháp công nghệ xanh', Icon: Sparkles },
  { id: 'about', label: 'Giới thiệu', Icon: Info },
];

export default function Sidebar({ page, onPage, filters, onFilter, countries, mobileOpen, setMobileOpen }) {
  const switchPage = (newPage) => { onPage(newPage); setMobileOpen(false); };
  return <>
    {mobileOpen && <div className="mobile-overlay" onClick={() => setMobileOpen(false)} />}
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand">
        <div className="brand-icon"><Leaf size={27} strokeWidth={2.4} /></div>
        <div><strong>GreenSegment <span>AI</span></strong><small>URBAN EMISSION INTELLIGENCE</small></div>
        <button className="mobile-close" aria-label="Đóng menu" onClick={() => setMobileOpen(false)}><X size={20}/></button>
      </div>
      <div className="sidebar-desc">Khám phá cấu trúc phát thải khí nhà kính và định hướng công nghệ xanh cho đô thị toàn cầu.</div>
      <div className="sidebar-divider" />
      <div className="nav-label">KHÁM PHÁ</div>
      <nav className="nav-list" aria-label="Điều hướng chính">
        {TABS.map(({ id, label, Icon }) => <button key={id} type="button"
          className={`nav-item ${page === id ? 'active' : ''}`}
          onClick={() => switchPage(id)} aria-current={page === id ? 'page' : undefined}>
          <Icon size={19}/><span>{label}</span>
        </button>)}
      </nav>
      <div className="sidebar-divider" />
      <div className="nav-label section-label"><SlidersHorizontal size={16}/> BỘ LỌC DỮ LIỆU</div>
      <label className="field-label" htmlFor="country-filter"><Globe2 size={16}/> Quốc gia / vùng lãnh thổ</label>
      <select id="country-filter" value={filters.country} onChange={(e) => onFilter('country', e.target.value)}>
        <option value="">Tất cả quốc gia</option>
        {countries.map((country) => <option key={country.name} value={country.name}>{country.name} ({country.count})</option>)}
      </select>
      <label className="field-label" htmlFor="cluster-filter"><Layers3 size={16}/> Cụm phát thải</label>
      <select id="cluster-filter" value={filters.cluster_id} onChange={(e) => onFilter('cluster_id', e.target.value)}>
        <option value="">Tất cả 3 cụm</option>
        <option value="0">Cụm 0 – Dân cư · Giao thông</option>
        <option value="1">Cụm 1 – Công nghiệp</option>
        <option value="2">Cụm 2 – Năng lượng</option>
      </select>
      <label className="field-label" htmlFor="sector-filter"><Leaf size={16}/> Lĩnh vực chiếm tỷ trọng cao nhất</label>
      <select id="sector-filter" value={filters.sector} onChange={(e) => onFilter('sector', e.target.value)}>
        <option value="">Tất cả lĩnh vực</option>
        {SECTORS.map((sector) => <option key={sector} value={sector}>{SECTOR_LABELS[sector]}</option>)}
      </select>
      <button className="filter-reset" onClick={() => { onFilter('reset'); }} type="button">Đặt lại bộ lọc</button>
      <div className="sidebar-spacer" />
      <div className="sidebar-footer"><span className="live-dot"/> EDGAR Cities 2024 <small>· K-Means (K=3)</small></div>
    </aside>
  </>;
}
