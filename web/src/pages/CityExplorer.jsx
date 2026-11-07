import React, { useEffect, useRef, useState } from 'react';
import { Building2, ChevronLeft, ChevronRight, Leaf, MapPin, Search, Sparkles } from 'lucide-react';
import { apiGet, apiPost } from '../api.js';
import { CLUSTER_COLORS, SECTORS, SECTOR_LABELS, ghg, num, pct, topSectors } from '../constants.js';
import { CitySectorChart } from '../components/SectorCharts.jsx';
import { Empty, ErrorBox, Loading, Note, Panel } from '../components/UI.jsx';

function signedDifference(value) {
  const magnitude = Math.round(Math.abs(value) * 100) / 100;
  return `${value < 0 && magnitude !== 0 ? '−' : '+'}${num(magnitude, 2)}`;
}

export default function CityExplorer({ filters, selectedCityId, onSelectCity }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [cities, setCities] = useState(null);
  const [details, setDetails] = useState(null);
  const [error, setError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [detailRefresh, setDetailRefresh] = useState(0);
  const [reports, setReports] = useState({});
  const [aiError, setAiError] = useState('');
  const [busy, setBusy] = useState(false);
  const aiRequest = useRef(null);

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
    setDetails(null); setDetailError('');
    if (!selectedCityId) return;
    const controller = new AbortController();
    apiGet(`/cities/${encodeURIComponent(selectedCityId)}`, {}, { signal: controller.signal })
      .then((result) => { if (!controller.signal.aborted) setDetails(result); })
      .catch((e) => { if (!controller.signal.aborted) setDetailError(e.message); });
    return () => controller.abort();
  }, [selectedCityId, detailRefresh]);

  useEffect(() => {
    setBusy(false); setAiError('');
    return () => { aiRequest.current?.abort(); aiRequest.current = null; };
  }, [selectedCityId]);

  async function analyze() {
    const controller = new AbortController();
    aiRequest.current = controller;
    const cityId = selectedCityId;
    setBusy(true); setAiError('');
    try {
      const result = await apiPost(`/cities/${encodeURIComponent(cityId)}/interpret`, {}, { signal: controller.signal });
      if (!controller.signal.aborted) setReports((prev) => ({ ...prev, [cityId]: result }));
    } catch (e) { if (!controller.signal.aborted) setAiError(e.message); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }

  // Never show the preceding city's profile during a selection change.
  const current = details?.city_id === selectedCityId ? details : null;
  const analysis = current?.analysis;
  const shares = analysis?.shares_percent;
  const cluster = analysis?.cluster;
  const position = analysis?.position_in_cluster;
  const report = reports[selectedCityId]?.report;
  return <div className="page-enter city-explorer">
    <div className="page-intro"><div><div className="eyebrow">KHÁM PHÁ / ĐÔ THỊ</div><h1>City Explorer</h1>
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
        {detailError && <><ErrorBox message={detailError}/><button className="button button-outline" onClick={() => setDetailRefresh((n) => n + 1)}>Tải lại hồ sơ</button></>}
        {!selectedCityId ? <Panel className="selection-placeholder"><div className="empty-detail"><Building2 size={42}/><h2>Chọn một đô thị để bắt đầu</h2>
          <p>Chọn trong danh sách bên trái hoặc nhấn trực tiếp vào một điểm trên bản đồ Tổng quan. Lọc quốc gia trong sidebar.</p></div></Panel> : !current ? !detailError && <Panel><Loading text="Đang đọc hồ sơ đô thị..."/></Panel> : <>
          <Panel className="city-hero-panel">
            <div className="city-hero"><div><span className="eyebrow">HỒ SƠ ĐÔ THỊ · EDGAR 2024</span>
              <h2>{current.city_name}</h2><p><MapPin size={16}/>{current.country_name} · Mã đô thị {current.city_id}</p></div>
              <span className="cluster-chip" style={{ color: CLUSTER_COLORS[current.cluster_id], borderColor: `${CLUSTER_COLORS[current.cluster_id]}55` }}>
                <i style={{ background: CLUSTER_COLORS[current.cluster_id] }}/> Cụm {current.cluster_id} · {cluster?.short_name}
              </span></div>
            <div className="city-metrics"><div><span>Tổng GHG 2024</span><strong>{ghg(current.ghg_total_2024)}</strong><small>Đơn vị gốc EDGAR*</small></div>
              <div><span>Lĩnh vực lớn nhất</span><strong>{SECTOR_LABELS[topSectors(shares, 1)[0]]}</strong><small>{pct(shares[topSectors(shares, 1)[0]], 2)} trong cơ cấu</small></div>
              <div><span>Khoảng cách tới tâm cụm</span><strong>{num(analysis.distance_to_centroid, 4)}</strong><small>Euclid · tỷ trọng gốc 0–1</small></div>
            </div>
          </Panel>
          <Panel title="Đô thị và tâm K-Means" subtitle="So sánh 7 tỷ trọng GHG với tâm mô hình đã lưu">
            <CitySectorChart shares={shares} clusterCentroid={cluster.centroid_percent}/>
            <div className="comparison-note"><Leaf size={17}/>
              <span>Chênh lệch so với tâm nổi bật theo độ lớn: {analysis.notable_differences.map(({ sector, difference_pp: d }) => `${SECTOR_LABELS[sector]} ${signedDifference(d)} điểm phần trăm`).join(' · ')}. Đây là mô tả, không phải kiểm định thống kê.</span>
            </div>
          </Panel>
          <Panel title="Phát thải và cơ cấu 7 lĩnh vực" subtitle="GHG giữ nguyên đơn vị gốc EDGAR · Tỷ trọng: % · Chênh lệch: điểm phần trăm">
            <div className="ce-table-scroll"><table className="ce-table city-emissions-table">
              <thead><tr>{['Lĩnh vực', 'GHG 2024', 'Đô thị (%)', 'Tâm (%)', 'Chênh lệch với tâm'].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead>
              <tbody>{SECTORS.map((s) => <tr key={s} className={analysis.notable_differences.some((d) => d.sector === s) ? 'city-notable-row' : ''}>
                <th scope="row">{SECTOR_LABELS[s]}</th>
                <td data-label="GHG 2024"><span>{num(analysis.emissions_by_sector[s], 2)}</span></td>
                <td data-label="Tỷ trọng đô thị"><span>{pct(shares[s], 2)}</span></td>
                <td data-label="Tỷ trọng tâm"><span>{pct(cluster.centroid_percent[s], 2)}</span></td>
                <td data-label="Chênh lệch với tâm" className="city-difference-cell"><span><strong>{signedDifference(analysis.comparison_to_centroid_pp[s])}</strong><span className="city-difference-unit">điểm phần trăm</span></span></td>
              </tr>)}</tbody>
            </table></div><Note>Ba dòng tô nền có chênh lệch tuyệt đối lớn nhất với tâm; đây không phải ngưỡng bất thường.</Note>
          </Panel>
          <Panel title="Vị trí trong phân bố khoảng cách của cụm" subtitle={`${num(position.reference_city_count)} đô thị cùng cụm ${current.cluster_id} · Không phụ thuộc bộ lọc tra cứu`}>
            <dl className="city-distance-grid city-distance-summary">
              <div><dt>Khoảng cách đô thị</dt><dd>{num(analysis.distance_to_centroid, 4)}</dd></div>
              <div><dt>Trung vị cụm</dt><dd>{num(cluster.distance_statistics.median, 4)}</dd></div>
              <div><dt>Phân vị thực nghiệm</dt><dd>{pct(position.percentile_rank_percent, 2)}</dd></div>
            </dl>
            <div className="city-position-hero"><p>{position.summary}</p><p>{num(position.count_at_or_below)} / {num(position.reference_city_count)} đô thị có khoảng cách tới tâm không lớn hơn đô thị này, bao gồm chính đô thị và các khoảng cách bằng nhau.</p></div>
            <Note>{position.note} Khoảng cách được tính trên cơ cấu tương đối, không đánh giá chất lượng môi trường.</Note>
          </Panel>
          <details className="panel city-extended-statistics"><summary>Xem thống kê mở rộng của cụm</summary><div className="city-extended-content">
            <h3>Các mốc khoảng cách bổ sung</h3>
            <dl className="city-distance-grid">{[['q1', 'Q1 cụm'], ['q3', 'Q3 cụm'], ['p90', 'P90 cụm'], ['p95', 'P95 cụm']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{num(cluster.distance_statistics[key], 4)}</dd></div>)}</dl>
            <h3>Thống kê lĩnh vực trong cụm</h3><p className="ce-scope">Trung bình/trung vị: % · Độ lệch chuẩn tổng thể/IQR: điểm phần trăm</p>
            <div className="ce-table-scroll"><table className="ce-table city-cluster-table"><thead><tr>{['Lĩnh vực', 'Trung bình', 'Trung vị', 'Độ lệch chuẩn', 'IQR'].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead>
              <tbody>{SECTORS.map((s) => <tr key={s}><th scope="row">{SECTOR_LABELS[s]}</th>{['mean', 'median', 'std', 'iqr'].map((key) => <td key={key}>{num(cluster.sector_statistics_percent[s][key], 2)}</td>)}</tr>)}</tbody>
            </table></div><Note>Tâm lấy từ mô hình; trung bình và trung vị tính từ các thành viên. Hai giá trị tâm và trung bình có thể lệch nhẹ.</Note>
          </div></details>
          <Panel title={<><Sparkles size={20}/> Phân tích hồ sơ đô thị bằng Gemini</>} subtitle="Báo cáo 250–400 từ, tập trung diễn giải cơ cấu và mức độ tương đồng với cụm">
            <div className="ce-ai-action"><p>Dữ liệu được Python kiểm tra và làm tròn trước khi gửi.</p><button className="button button-primary" disabled={busy} onClick={analyze}><Sparkles size={16}/>{busy ? 'Đang phân tích…' : 'Phân tích bằng Gemini'}</button></div>
            {busy && <Loading text={`Gemini đang phân tích ${current.city_name}…`}/>}
            {aiError && <ErrorBox message={aiError}/>}
            <div aria-live="polite">{report ? <article className="ce-report">
              <p className="ce-scope">{current.city_name} · {reports[selectedCityId].model} · Nội dung AI cần đối chiếu thống kê</p>
              <h3>Cơ cấu phát thải nổi bật</h3><p>{report.summary}</p>
              <h3>So sánh với đặc trưng cụm</h3><ul>{report.comparisons.map((text, i) => <li key={i}>{text}</li>)}</ul>
              <h3>Mức độ điển hình và tính đại diện</h3><p>{report.dispersion_and_representativeness}</p>
              <h3>Hạn chế và hướng nghiên cứu</h3><ul>{report.limitations.map((text, i) => <li key={`l-${i}`}>{text}</li>)}</ul><ul>{report.research_questions.map((text, i) => <li key={`q-${i}`}>{text}</li>)}</ul>
            </article> : !busy && <p className="ce-scope">Chưa phân tích đô thị này. Nhấn nút để tạo báo cáo Gemini từ dữ liệu đang hiển thị.</p>}</div>
          </Panel>
          <Note>*Đơn vị phát thải được giữ nguyên từ EDGAR. Các tỷ trọng không cho biết nhu cầu mua hay tính khả thi triển khai công nghệ.</Note>
        </>}
      </div>
    </div>
  </div>;
}
