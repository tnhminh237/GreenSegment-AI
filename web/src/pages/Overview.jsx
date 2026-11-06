import React, { useEffect, useState } from 'react';
import { Building2, Globe2, Layers3, MapPinned, Network, RefreshCw } from 'lucide-react';
import { apiGet } from '../api.js';
import { CLUSTER_COLORS, SECTOR_LABELS, num, pct, topSectors } from '../constants.js';
import { ClusterStackedChart } from '../components/SectorCharts.jsx';
import WorldMap from '../components/WorldMap.jsx';
import { Empty, ErrorBox, Loading, Note, Panel } from '../components/UI.jsx';

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
  const groups = stats?.clusters ?? [];

  return <div className="page-enter">
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
      <div className="overview-grid">
        <Panel title={<><MapPinned size={20}/> Bản đồ phân cụm đô thị</>} subtitle="Nhấn vào điểm đô thị để xem chi tiết" className="map-panel"
          action={<button type="button" className="icon-button" title="Tải lại" onClick={() => setRefresh((n) => n + 1)}><RefreshCw size={17}/></button>}>
          {mapError && <ErrorBox message={mapError} />}
          <WorldMap points={mapData?.points ?? []} onSelectCity={onSelectCity}/>
          <p className="map-caption">{mapData ? `Đang hiển thị ${num(mapData.shown)} / ${num(mapData.total_matching)} đô thị${mapData.sampled ? ' (lấy mẫu để bản đồ chạy mượt)' : ''}.` : 'Đang tải điểm đô thị...'} Nền bản đồ cần kết nối Internet.</p>
        </Panel>
        <Panel title={<><Layers3 size={20}/> Ba nhóm đô thị</>} subtitle={isFiltered ? 'Số lượng theo bộ lọc hiện tại; tỷ trọng theo dữ liệu gốc' : 'Quy mô và cấu trúc phát thải của từng cụm'} className="cluster-panel">
          <div className="cluster-list">
            {groups.map((c) => <div className="cluster-tile" key={c.cluster_id}>
              <div className="cluster-tile-left"><div className="cluster-number" style={{ color: CLUSTER_COLORS[c.cluster_id], backgroundColor: `${CLUSTER_COLORS[c.cluster_id]}14` }}>
                {c.cluster_id}</div><div><strong>{c.short_name}</strong>
                  <p>{topSectors(c.mean_sector_shares_percent, 2).map((s) => `${SECTOR_LABELS[s]} ${pct(c.mean_sector_shares_percent[s], 1)}`).join(' · ')}</p>
                </div></div>
              <div className="cluster-tile-right"><strong>{num(c.filtered_count)}</strong><small>{pct(c.filtered_percentage, 1)}</small></div>
            </div>)}
          </div>
          <p className="cluster-footnote">Cụm được xác định từ 7 tỷ trọng phát thải, không phải 3 Scope.</p>
        </Panel>
      </div>
      <Panel title="Cơ cấu phát thải trung bình theo cụm" subtitle={isFiltered ? 'Trung bình tỷ trọng của các đô thị thỏa điều kiện lọc trong mỗi cụm' : 'Trung bình tỷ trọng 7 lĩnh vực của các đô thị thuộc từng cụm'}>
        {stats.filtered_cities ? <ClusterStackedChart clusters={groups} filtered={isFiltered}/>: <Empty>Không có đô thị thỏa bộ lọc. Hãy điều chỉnh bộ lọc bên trái.</Empty>}
        <Note>Biểu đồ thể hiện <strong>trung bình tỷ trọng theo từng đô thị</strong>, không phải tỷ trọng của tổng lượng phát thải cộng dồn trong cụm. Đơn vị phát thải tuyệt đối chưa được xác minh.</Note>
      </Panel>
    </>}
  </div>;
}
