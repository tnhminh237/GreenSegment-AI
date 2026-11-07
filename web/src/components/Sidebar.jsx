import React from 'react';
import { BarChart3, Info, Leaf, Search, Telescope, X } from 'lucide-react';

const TABS = [
  { id: 'overview', label: 'Tổng quan', Icon: BarChart3 },
  { id: 'city', label: 'Tra cứu đô thị', Icon: Search },
  { id: 'market', label: 'Market Explorer', Icon: Telescope },
  { id: 'about', label: 'Giới thiệu', Icon: Info },
];

export default function Sidebar({ page, onPage, mobileOpen, setMobileOpen }) {
  const switchPage = (newPage) => { onPage(newPage); setMobileOpen(false); };
  return <>
    {mobileOpen && <div className="mobile-overlay" onClick={() => setMobileOpen(false)} />}
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand">
        <div className="brand-icon"><Leaf size={27} strokeWidth={2.4} /></div>
        <div><strong>GreenSegment <span>AI</span></strong></div>
        <button className="mobile-close" aria-label="Đóng menu" onClick={() => setMobileOpen(false)}><X size={20}/></button>
      </div>
      <div className="sidebar-desc">Phân tích cơ cấu phát thải đô thị và hỗ trợ khám phá thị trường công nghệ xanh.</div>
      <div className="sidebar-divider" />
      <div className="nav-label">KHÁM PHÁ</div>
      <nav className="nav-list" aria-label="Điều hướng chính">
        {TABS.map(({ id, label, Icon }) => <button key={id} type="button"
          className={`nav-item ${page === id ? 'active' : ''}`}
          onClick={() => switchPage(id)} aria-current={page === id ? 'page' : undefined}>
          <Icon size={19}/><span>{label}</span>
        </button>)}
      </nav>
    </aside>
  </>;
}
