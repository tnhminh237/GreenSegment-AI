import React, { useEffect, useState } from 'react';
import { Building2, Globe2, Layers3, MapPinned, Network, RefreshCw } from 'lucide-react';
import { apiGet } from '../api.js';
import { num } from '../constants.js';
import ClusterExplorer from './ClusterExplorer.jsx';
import WorldMap from '../components/WorldMap.jsx';
import { Empty, ErrorBox, Loading, Panel } from '../components/UI.jsx';

export default function Overview({ filters, onSelectCity }) {
  const [stats, setStats] = useState(null);
  const [mapData, setMapData] = useState(null);
  const [error, setError] = useState('');
  const [mapError, setMapError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const selected = {
    country: filters.country,
    cluster_id: filters.cluster_id === '' ? undefined : Number(filters.cluster_id),
    sector: filters.sector,
  };
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setMapError('');
    apiGet('/overview', selected, { signal: controller.signal })
      .then(setStats).catch((e) => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    apiGet('/cities/map', { ...selected, limit: 5000 }, { signal: controller.signal })
      .then(setMapData).catch((e) => { if (!controller.signal.aborted) setMapError(e.message); });
    return () => controller.abort();
  }, [filters.country, filters.cluster_id, filters.sector, refresh]);

  const isFiltered = !!(filters.country || filters.cluster_id !== '' || filters.sector);

  return <div className="page-enter overview-page">
    <div className="page-intro">
      <div><div className="eyebrow">DASHBOARD / TỔNG QUAN</div><h1>Bức tranh phát thải đô thị toàn cầu</h1>
        <p>Khám phá đặc điểm cơ cấu phát thải khí nhà kính của các đô thị qua mô hình phân cụm K-Means.</p>
      </div>
      <span className="year-pill"><span className="live-dot"/> Dữ liệu EDGAR 2024</span>
    </div>
    {error && <ErrorBox message={error} />}
    {loading && !stats ? <Loading/> : stats && <>
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-icon green"><Building2 size={23}/></div><span>Số đô thị {isFiltered ? 'phù hợp' : 'toàn cầu'}</span>
          <strong>{num(stats.filtered_cities)}</strong><small>{isFiltered ? `trên ${num(stats.total_cities)} đô thị` : 'Trong bộ dữ liệu nghiên cứu'}</small></div>
        <div className="stat-card"><div className="stat-icon blue"><Globe2 size={23}/></div><span>Quốc gia / vùng lãnh thổ</span>
          <strong>{num(stats.total_countries)}</strong><small>Trong toàn bộ dữ liệu</small></div>
        <div className="stat-card"><div className="stat-icon orange"><Layers3 size={23}/></div><span>Số cụm phát thải</span>
          <strong>{num(stats.total_clusters)}</strong><small>K-Means · K = 3</small></div>
        <div className="stat-card"><div className="stat-icon purple"><Network size={23}/></div><span>Đặc trưng phân nhóm</span>
          <strong>07</strong><small>Lĩnh vực phát thải GHG</small></div>
      </div>
        <Panel title={<><MapPinned size={20}/> Bản đồ phân cụm đô thị</>} subtitle="Nhấn vào điểm đô thị để xem chi tiết" className="map-panel"
          action={<button type="button" className="icon-button" title="Tải lại" onClick={() => setRefresh((n) => n + 1)}><RefreshCw size={17}/></button>}>
          {mapError && <ErrorBox message={mapError} />}
          <p className="ce-scope">Bản đồ và KPI số đô thị phía trên áp dụng bộ lọc quốc gia, lĩnh vực và cụm. Các KPI còn lại mô tả toàn bộ dữ liệu.</p>
          <WorldMap points={mapData?.points ?? []} onSelectCity={onSelectCity}/>
          {!mapError && mapData?.total_matching === 0 && <Empty>Không có đô thị thỏa bộ lọc. Hãy điều chỉnh bộ lọc bên trái.</Empty>}
          <p className="map-caption">{mapData ? `Đang hiển thị ${num(mapData.shown)} / ${num(mapData.total_matching)} đô thị${mapData.sampled ? ' (lấy mẫu để bản đồ chạy mượt)' : ''}.` : 'Đang tải điểm đô thị...'} Nền bản đồ cần kết nối Internet.</p>
        </Panel>
    </>}
    <ClusterExplorer/>
  </div>;
}
