import React, { useEffect, useState } from 'react';
import { ArrowRight, Building2, ChevronLeft, ChevronRight, Leaf, MapPin, Search, Sparkles } from 'lucide-react';
import { apiGet } from '../api.js';
import { CLUSTER_COLORS, SECTOR_LABELS, ghg, num, pct, topSectors } from '../constants.js';
import { CitySectorChart, SectorProgress } from '../components/SectorCharts.jsx';
import { Empty, ErrorBox, Loading, Note, Panel } from '../components/UI.jsx';

export default function CityExplorer({ filters, selectedCityId, onSelectCity, onGoAdvisor }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [cities, setCities] = useState(null);
  const [details, setDetails] = useState(null);
  const [error, setError] = useState('');
  const [detailError, setDetailError] = useState('');

  useEffect(() => { setPage(1); }, [search, filters.country, filters.cluster_id, filters.sector]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setError('');
      apiGet('/cities', { search, country: filters.country, cluster_id: filters.cluster_id,
        sector: filters.sector, page, page_size: 10 }, { signal: controller.signal })
        .then(setCities).catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [search, filters.country, filters.cluster_id, filters.sector, page]);

  useEffect(() => {
    if (!selectedCityId) { setDetails(null); return; }
    const controller = new AbortController();
    setDetailError('');
    apiGet(`/cities/${encodeURIComponent(selectedCityId)}`, {}, { signal: controller.signal })
      .then(setDetails).catch((e) => { if (!controller.signal.aborted) setDetailError(e.message); });
    return () => controller.abort();
  }, [selectedCityId]);

  const shares = details?.shares_percent;
  const cluster = details?.cluster;
  return <div className="page-enter">
    <div className="page-intro"><div><div className="eyebrow">KHÁM PHÁ / ĐÔ THỊ</div><h1>Tra cứu hồ sơ phát thải đô thị</h1>
      <p>Tìm đô thị theo tên, xem tỷ trọng 7 lĩnh vực và so sánh với đặc trưng của cụm K-Means.</p></div></div>
    <div className="city-layout">
      <Panel title={<><Search size={20}/> Tìm đô thị</>} subtitle="Chọn đô thị trong danh sách để mở hồ sơ" className="city-search-panel">
        <div className="search-input-wrap"><Search size={18}/><input placeholder="Nhập tên đô thị hoặc quốc gia..." value={search}
          onChange={(e) => setSearch(e.target.value)} aria-label="Tìm đô thị"/></div>
        <div className="result-count">{cities ? `${num(cities.total)} đô thị phù hợp` : 'Đang tìm kiếm...'}</div>
        {error && <ErrorBox message={error}/>} 
        <div className="city-result-list">
          {cities?.items?.map((city) => <button type="button" key={city.city_id}
            className={`city-result ${selectedCityId === city.city_id ? 'selected' : ''}`} onClick={() => onSelectCity(city.city_id)}>
            <span className="result-cluster" style={{ background: CLUSTER_COLORS[city.cluster_id] }}/>
            <span><strong>{city.city_name}</strong><small><MapPin size={12}/>{city.country_name} · Cụm {city.cluster_id}</small></span>
            <ChevronRight size={17}/>
          </button>)}
          {cities && !cities.total && <Empty>Không có đô thị phù hợp. Bạn có thể đặt lại bộ lọc trong menu.</Empty>}
        </div>
        {cities && cities.total > cities.page_size && <div className="pagination">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft size={16}/> Trước</button>
          <span>{page} / {Math.ceil(cities.total / cities.page_size)}</span>
          <button disabled={page >= Math.ceil(cities.total / cities.page_size)} onClick={() => setPage((p) => p + 1)}>Sau <ChevronRight size={16}/></button>
        </div>}
      </Panel>
      <div className="city-detail-stack">
        {detailError && <ErrorBox message={detailError}/>} 
        {!selectedCityId ? <Panel className="selection-placeholder"><div className="empty-detail"><Building2 size={42}/><h2>Chọn một đô thị để bắt đầu</h2>
          <p>Chọn trong danh sách bên trái hoặc nhấn trực tiếp vào một điểm trên bản đồ Tổng quan.</p></div></Panel> : !details ? <Panel><Loading text="Đang đọc hồ sơ đô thị..."/></Panel> : <>
          <Panel className="city-hero-panel">
            <div className="city-hero"><div><span className="eyebrow">HỒ SƠ ĐÔ THỊ · EDGAR 2024</span>
              <h2>{details.city_name}</h2><p><MapPin size={16}/>{details.country_name}</p></div>
              <span className="cluster-chip" style={{ color: CLUSTER_COLORS[details.cluster_id], borderColor: `${CLUSTER_COLORS[details.cluster_id]}55` }}>
                <i style={{ background: CLUSTER_COLORS[details.cluster_id] }}/> Cụm {details.cluster_id} · {cluster?.short_name}
              </span></div>
            <div className="city-metrics"><div><span>Tổng GHG 2024</span><strong>{ghg(details.ghg_total_2024)}</strong><small>Đơn vị gốc EDGAR*</small></div>
              <div><span>Lĩnh vực lớn nhất</span><strong>{SECTOR_LABELS[topSectors(shares, 1)[0]]}</strong><small>{pct(shares[topSectors(shares, 1)[0]], 2)} trong cơ cấu</small></div>
              <div><span>Khoảng cách tới tâm cụm</span><strong>{num(details.distance_to_centroid, 3)}</strong><small>Trong không gian 7 tỷ trọng</small></div>
            </div>
          </Panel>
          <Panel title="So sánh cơ cấu phát thải" subtitle="Tỷ trọng từng lĩnh vực của đô thị và tỷ trọng trung bình của cụm">
            <CitySectorChart shares={shares} clusterMeans={cluster?.mean_sector_shares_percent}/>
            <div className="comparison-note"><Leaf size={17}/>
              {(() => { const items = Object.entries(details.comparison_percentage_points)
                .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 2);
                return <span>Chênh lệch nổi bật theo độ lớn: {items.map(([s, d]) => `${SECTOR_LABELS[s]} ${d > 0 ? '+' : ''}${num(d, 2)} điểm %`).join(' · ')}. Đây là mô tả, không phải kiểm định thống kê.</span>;
              })()}
            </div>
          </Panel>
          <Panel title="Tỷ trọng GHG theo 7 lĩnh vực" subtitle="Tổng tỷ trọng của mỗi đô thị xấp xỉ 100%">
            <SectorProgress shares={shares}/>
          </Panel>
          <div className="city-advisor-cta"><div><Sparkles size={21}/><span><strong>Khám phá hướng công nghệ xanh</strong><small>Dùng Gemini giải thích cơ cấu phát thải và gợi ý giải pháp có nguồn.</small></span></div>
            <button type="button" className="button button-primary" onClick={onGoAdvisor}>Xem gợi ý AI <ArrowRight size={16}/></button></div>
          <Note>*Đơn vị phát thải được giữ nguyên từ EDGAR. Các tỷ trọng không cho biết nhu cầu mua hay tính khả thi triển khai công nghệ.</Note>
        </>}
      </div>
    </div>
  </div>;
}
