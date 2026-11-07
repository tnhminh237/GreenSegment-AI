import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Sparkles } from 'lucide-react';
import { apiGet, apiPost } from '../api.js';
import { SECTOR_LABELS, SECTOR_COLORS, num, pct, topSectors } from '../constants.js';
import { ClusterStackedChart } from '../components/SectorCharts.jsx';
import { ErrorBox, Loading, Note, Panel } from '../components/UI.jsx';

export default function ClusterExplorer({ selectorContainer = null }) {
  const [stats, setStats] = useState(null);
  const [selected, setSelected] = useState(0);
  const [error, setError] = useState('');
  const [reports, setReports] = useState({});
  const [aiError, setAiError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const request = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    apiGet('/cluster-explorer', {}, { signal: controller.signal }).then(setStats)
      .catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => () => request.current?.abort(), []);

  function selectCluster(id) {
    request.current?.abort(); request.current = null;
    setBusy(false); setAiError(''); setSelected(id);
  }
  async function analyze() {
    const controller = new AbortController();
    request.current = controller;
    setBusy(true); setAiError('');
    try {
      const result = await apiPost(`/cluster-explorer/${selected}/interpret`, {}, { signal: controller.signal });
      if (!controller.signal.aborted) setReports((prev) => ({ ...prev, [selected]: result }));
    } catch (e) { if (!controller.signal.aborted) setAiError(e.message); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const cluster = stats?.clusters.find((c) => c.cluster_id === selected);
  const report = reports[selected]?.report;
  const highlights = cluster ? topSectors(cluster.centroid_percent, 3) : [];
  const selector = cluster && <div className="ce-selector" role="group" aria-label="Chọn cụm K-Means">
    {stats.clusters.map((c) => <button key={c.cluster_id} type="button" aria-pressed={selected === c.cluster_id}
      aria-label={`Cụm ${c.cluster_id} · ${c.short_name}: ${num(c.city_count)} đô thị · ${pct(c.city_percentage, 2)} toàn bộ dữ liệu. Chọn hồ sơ cụm.`}
      className={selected === c.cluster_id ? 'selected' : ''} style={{ '--cluster-color': c.color }} onClick={() => selectCluster(c.cluster_id)}>
      <span><small className="ce-cluster-label">Cụm {c.cluster_id}</small><strong>{c.short_name}</strong>
        <small className="ce-cluster-size"><span>{num(c.city_count)}<span className="ce-cluster-unit"> đô thị</span></span><span className="ce-cluster-separator"> · </span><span>{pct(c.city_percentage, 2)}</span></small></span>
    </button>)}
  </div>;

  return <section className="cluster-explorer overview-clusters" aria-labelledby="cluster-exploration-title">
    <header className="ce-section-heading">
      <h2 id="cluster-exploration-title">Khám phá các cụm đô thị</h2>
      <p>So sánh ba nhóm đô thị và tìm hiểu đặc điểm của từng cụm.</p>
    </header>
    {error && <><ErrorBox message={error}/><button className="button button-outline" onClick={() => setRefresh((n) => n + 1)}>Tải lại dữ liệu</button></>}
    {!stats && !error && <Loading/>}
    {cluster && <>
      {selectorContainer ? createPortal(selector, selectorContainer) : selector}
      <div className="ce-exploration-grid">
        <Panel className="ce-overview-chart" title="So sánh cơ cấu GHG của ba cụm" subtitle="7 tỷ trọng tại tâm K-Means · Mỗi cụm tương ứng 100%">
          <ClusterStackedChart clusters={stats.clusters} basis="centroid" selectedClusterId={selected} onSelectCluster={selectCluster}/>
          <p className="ce-chart-hint">Nhấn vào thanh hoặc tên cụm để xem hồ sơ.</p>
        </Panel>
        <Panel className="ce-cluster-profile" title={<><span className="ce-profile-id" style={{ color: cluster.color }}>Cụm {selected}</span><span className="ce-profile-name">{cluster.short_name}</span></>}>
          <dl className="ce-profile-kpis">
            <div><dt>Số đô thị trong cụm</dt><dd>{num(cluster.city_count)}</dd></div>
            <div><dt>Tỷ lệ trong toàn bộ dữ liệu</dt><dd>{pct(cluster.city_percentage, 2)}</dd></div>
          </dl>
          <h3 className="ce-profile-subheading">Ba lĩnh vực nổi bật tại tâm K-Means</h3>
          <ul className="ce-highlights">{highlights.map((sector) => <li key={sector}>
            <div className="ce-highlight-heading"><span>{SECTOR_LABELS[sector]}</span><strong>{pct(cluster.centroid_percent[sector], 2)}</strong></div>
            <div className="progress-track" role="progressbar" aria-label={SECTOR_LABELS[sector]} aria-valuenow={cluster.centroid_percent[sector]} aria-valuemin={0} aria-valuemax={100}>
              <div style={{ background: SECTOR_COLORS[sector], width: `${cluster.centroid_percent[sector]}%` }}/>
            </div>
          </li>)}</ul>
          <p className="ce-profile-scope">Quy mô trên toàn bộ {num(stats.total_cities)} đô thị.</p>
        </Panel>
      </div>
      <Panel title={<><Sparkles size={20}/> Gemini diễn giải cụm</>} subtitle="Tìm hiểu đặc điểm nổi bật và sự khác biệt giữa các nhóm đô thị">
        <div className="ce-ai-action"><p>Nhận diễn giải dễ đọc cho cụm đang chọn.</p>
          <button className="button button-primary" disabled={busy} onClick={analyze}><Sparkles size={16}/>{busy ? 'Đang phân tích…' : 'Gemini diễn giải cụm'}</button></div>
        {busy && <Loading text={`Gemini đang diễn giải cụm ${selected}…`}/>}
        {aiError && <ErrorBox message={aiError}/>}
        <div aria-live="polite">{report ? <article className="ce-report">
          <p className="ce-scope">Diễn giải cho Cụm {selected} · Nội dung AI cần được đối chiếu với dữ liệu.</p>
          <h3>Đặc điểm nổi bật</h3><p>{report.summary}</p>
          <h3>So sánh các cụm</h3><ul>{report.comparisons.map((v, i) => <li key={i}>{v}</li>)}</ul>
          <h3>Mức độ tương đồng trong cụm</h3><p>{report.dispersion_and_representativeness}</p>
          <h3>Hạn chế và hướng nghiên cứu</h3><ul>{report.limitations.map((v, i) => <li key={`limit-${i}`}>{v}</li>)}</ul>
          <ul>{report.research_questions.map((v, i) => <li key={`research-${i}`}>{v}</li>)}</ul>
        </article> : !busy && <p className="ce-scope">Chưa có báo cáo cho cụm này. Nhấn nút để gửi thống kê tới Gemini.</p>}</div>
      </Panel>
      <Note>Dữ liệu EDGAR 2024 · K-Means K=3, phân cụm dựa trên 7 tỷ trọng GHG. Kết quả không suy ra nguyên nhân phát thải hay tính khả thi công nghệ.</Note>
    </>}
  </section>;
}
