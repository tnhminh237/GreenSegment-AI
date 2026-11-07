import React from 'react';
import { Globe2, Layers3, Leaf, SlidersHorizontal } from 'lucide-react';
import { SECTORS, SECTOR_LABELS } from '../constants.js';

export default function DataFilters({ filters, onFilter, countries, inline = false }) {
  return <section className={`data-filters ${inline ? 'data-filters-inline' : ''}`} aria-label="Bộ lọc dữ liệu">
    {!inline && <div className="nav-label section-label"><SlidersHorizontal size={16}/> BỘ LỌC DỮ LIỆU</div>}
    <div className="filters-grid">
      <div>
        <label className="field-label" htmlFor="country-filter"><Globe2 size={16}/> Quốc gia / vùng lãnh thổ</label>
        <select id="country-filter" value={filters.country} onChange={(e) => onFilter('country', e.target.value)}>
          <option value="">Tất cả quốc gia</option>
          {countries.map((country) => <option key={country.name} value={country.name}>{country.name} ({country.count})</option>)}
        </select>
      </div>
      <div>
        <label className="field-label" htmlFor="cluster-filter"><Layers3 size={16}/> Cụm phát thải</label>
        <select id="cluster-filter" value={filters.cluster_id} onChange={(e) => onFilter('cluster_id', e.target.value)}>
          <option value="">Tất cả 3 cụm</option>
          <option value="0">Cụm 0 – Dân cư · Giao thông</option>
          <option value="1">Cụm 1 – Công nghiệp</option>
          <option value="2">Cụm 2 – Năng lượng</option>
        </select>
      </div>
      <div>
        <label className="field-label" htmlFor="sector-filter"><Leaf size={16}/> Lĩnh vực chiếm tỷ trọng cao nhất</label>
        <select id="sector-filter" value={filters.sector} onChange={(e) => onFilter('sector', e.target.value)}>
          <option value="">Tất cả lĩnh vực</option>
          {SECTORS.map((sector) => <option key={sector} value={sector}>{SECTOR_LABELS[sector]}</option>)}
        </select>
      </div>
    </div>
    <button className="filter-reset" onClick={() => onFilter('reset')} type="button">Đặt lại bộ lọc</button>
  </section>;
}
