import React, { useEffect, useState } from 'react';
import { ArrowUpRight, Menu } from 'lucide-react';
import { apiGet } from './api.js';
import Sidebar from './components/Sidebar.jsx';
import Overview from './pages/Overview.jsx';
import CityExplorer from './pages/CityExplorer.jsx';
import GreenAdvisor from './pages/GreenAdvisor.jsx';
import About from './pages/About.jsx';
import ClusterExplorer from './pages/ClusterExplorer.jsx';

const INITIAL_FILTERS = { country: '', cluster_id: '', sector: '' };

export default function App() {
  const [page, setPage] = useState('overview');
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [countries, setCountries] = useState([]);
  const [selectedCityId, setSelectedCityId] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    apiGet('/countries').then(setCountries).catch(() => {});
  }, []);

  const onFilter = (key, value) => setFilters((prev) => key === 'reset' ? INITIAL_FILTERS : { ...prev, [key]: value });
  const onSelectCityFromMap = (cityId) => { setSelectedCityId(String(cityId)); setPage('city'); window.scrollTo({ top: 0, behavior: 'smooth' }); };

  return <div className="app-shell">
    <Sidebar page={page} onPage={setPage} filters={filters} onFilter={onFilter}
      countries={countries} mobileOpen={mobileOpen} setMobileOpen={setMobileOpen}/>
    <div className="main-shell">
      <div className="mobile-topbar"><button aria-label="Mở điều hướng" onClick={() => setMobileOpen(true)}><Menu size={22}/></button>
        <strong>GreenSegment AI</strong><span>2024</span></div>
      <div className="main-inner">
        <div className="utility-bar"><span>GREEN INTELLIGENCE PLATFORM</span>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API Docs <ArrowUpRight size={13}/></a></div>
        {page === 'overview' && <Overview filters={filters} onSelectCity={onSelectCityFromMap}/>}
        {page === 'clusters' && <ClusterExplorer/>}
        {page === 'city' && <CityExplorer filters={filters} selectedCityId={selectedCityId}
          onSelectCity={(id) => setSelectedCityId(String(id))} onGoAdvisor={() => { setPage('advisor'); window.scrollTo(0, 0); }}/>} 
        {page === 'advisor' && <GreenAdvisor selectedCityId={selectedCityId} onSelectCity={(id) => setSelectedCityId(String(id))}/>}
        {page === 'about' && <About/>}
      </div>
    </div>
  </div>;
}
