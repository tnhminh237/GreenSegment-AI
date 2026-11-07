import React, { useEffect, useRef, useState } from 'react';
import { Building2, ChartNoAxesCombined, Layers3, Sparkles } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { apiGet, apiPost } from '../api.js';
import { SECTORS, SECTOR_LABELS, num, pct } from '../constants.js';
import { ClusterStackedChart } from '../components/SectorCharts.jsx';
import { ErrorBox, Loading, Note, Panel } from '../components/UI.jsx';

export default function ClusterExplorer() {
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
  const rows = cluster && SECTORS.map((s) => ({ name: SECTOR_LABELS[s],
    centroid: cluster.centroid_percent[s], mean: cluster.sector_statistics_percent[s].mean,
    median: cluster.sector_statistics_percent[s].median }));
  const distance = cluster?.distance_statistics;

  return <div className="page-enter cluster-explorer">
    <div className="page-intro"><div><div className="eyebrow">KHÁM PHÁ / CẤU TRÚC CỤM</div>
      <h1>Cluster Explorer</h1><p>Đọc cấu trúc phát thải, so sánh ba cụm và khám phá mức độ đa dạng bên trong mỗi nhóm đô thị.</p>
    </div><span className="year-pill"><span className="live-dot"/> EDGAR 2024 · K-Means</span></div>
    {error && <><ErrorBox message={error}/><button className="button button-outline" onClick={() => setRefresh((n) => n + 1)}>Tải lại thống kê</button></>}
    {!stats && !error && <Loading/>}
    {cluster && <>
      <div className="ce-selector" role="group" aria-label="Chọn cụm K-Means">
        {stats.clusters.map((c) => <button key={c.cluster_id} aria-pressed={selected === c.cluster_id}
          className={selected === c.cluster_id ? 'selected' : ''} style={{ '--cluster-color': c.color }} onClick={() => selectCluster(c.cluster_id)}>
          <span className="ce-cluster-id">0{c.cluster_id + 1}</span><span><small>Cụm {c.cluster_id}</small><strong>{c.short_name}</strong><small>{num(c.city_count)} đô thị · {pct(c.city_percentage, 2)}</small></span>
        </button>)}
      </div>
      <p className="ce-scope">Thống kê toàn bộ dữ liệu của cụm, độc lập với bộ lọc sidebar.</p>
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-icon green"><Building2 size={23}/></div><span>Đô thị trong cụm {selected}</span><strong>{num(cluster.city_count)}</strong><small>{cluster.short_name}</small></div>
        <div className="stat-card"><div className="stat-icon blue"><Layers3 size={23}/></div><span>Tỷ lệ đô thị</span><strong>{pct(cluster.city_percentage, 2)}</strong><small>Trong {num(stats.total_cities)} đô thị</small></div>
        <div className="stat-card"><div className="stat-icon orange"><ChartNoAxesCombined size={23}/></div><span>Khoảng cách trung vị</span><strong>{num(distance.median, 4)}</strong><small>Euclid · tỷ trọng 0–1</small></div>
        <div className="stat-card"><div className="stat-icon purple"><ChartNoAxesCombined size={23}/></div><span>IQR khoảng cách</span><strong>{num(distance.iqr, 4)}</strong><small>Q3 − Q1 · không có đơn vị</small></div>
      </div>
      <div className="ce-chart-grid">
        <Panel title={`Cơ cấu GHG · Cụm ${selected}`} subtitle="Tâm K-Means, trung bình và trung vị theo từng đô thị">
          <div className="ce-profile-chart"><ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 15, top: 8, bottom: 8 }}>
              <CartesianGrid horizontal={false} strokeDasharray="3 5" stroke="#edf1f2"/>
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }}/>
              <YAxis type="category" dataKey="name" width={85} tick={{ fontSize: 11 }}/>
              <Tooltip formatter={(value) => pct(value, 3)}/><Legend/>
              <Bar dataKey="centroid" name="Tâm K-Means" fill={cluster.color} maxBarSize={12}/>
              <Bar dataKey="mean" name="Trung bình" fill="#075944" maxBarSize={12}/>
              <Bar dataKey="median" name="Trung vị" fill="#b9dcd0" maxBarSize={12}/>
            </BarChart>
          </ResponsiveContainer></div>
        </Panel>
        <Panel title="Đối chiếu ba cụm" subtitle="Trung bình tỷ trọng, không gia quyền theo lượng GHG">
          <ClusterStackedChart clusters={stats.clusters}/>
          <div className="ce-comparison">{stats.clusters.filter((c) => c.cluster_id !== selected).map((other) => {
            const gaps = cluster.comparison_percentage_points[other.cluster_id];
            const sector = [...SECTORS].sort((a, b) => Math.abs(gaps[b]) - Math.abs(gaps[a]))[0];
            return <p key={other.cluster_id}>So với cụm {other.cluster_id}, chênh lệch lớn nhất ở <strong>{SECTOR_LABELS[sector]}</strong>: <strong>{gaps[sector] > 0 ? '+' : ''}{num(gaps[sector], 2)} điểm %</strong>.</p>;
          })}</div>
        </Panel>
      </div>
      <Panel title="Độ phân tán theo lĩnh vực" subtitle="Tỷ trọng: % · Độ lệch chuẩn và IQR: điểm phần trăm · Độ lệch chuẩn tổng thể (ddof=0)">
        <div className="ce-table-scroll"><table className="ce-table"><caption className="ce-scope">{cluster.cluster_name}</caption>
          <thead><tr>{['Lĩnh vực', 'Tâm', 'Trung bình', 'Trung vị', 'Độ lệch chuẩn', 'Q1', 'Q3', 'IQR'].map((t) => <th scope="col" key={t}>{t}</th>)}</tr></thead>
          <tbody>{SECTORS.map((s) => { const v = cluster.sector_statistics_percent[s]; return <tr key={s}><th scope="row">{SECTOR_LABELS[s]}</th>
            {[cluster.centroid_percent[s], v.mean, v.median, v.std, v.q1, v.q3, v.iqr].map((value, i) => <td key={i}>{num(value, 3)}</td>)}</tr>; })}</tbody>
        </table></div>
        <Note>Tâm lấy từ kết quả mô hình, trung bình tính lại từ nhãn cuối cùng. Chênh lệch lớn nhất giữa hai giá trị: {num(cluster.centroid_mean_max_gap_pp, 5)} điểm phần trăm.</Note>
      </Panel>
      <Panel title="Khoảng cách đến tâm K-Means" subtitle="Khoảng cách Euclid trên 7 tỷ trọng gốc (0–1), không phải phần trăm hoặc lượng phát thải">
        <dl className="ce-distance-grid">{[['min', 'Nhỏ nhất'], ['mean', 'Trung bình'], ['median', 'Trung vị'], ['std', 'Độ lệch chuẩn'], ['q1', 'Q1'], ['q3', 'Q3'], ['iqr', 'IQR'], ['p90', 'P90'], ['p95', 'P95'], ['max', 'Lớn nhất']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{num(distance[key], 4)}</dd></div>)}</dl>
        <Note>Khoảng cách lớn thể hiện cơ cấu khác tâm nhiều hơn, chưa đủ để kết luận là ngoại lệ hoặc đánh giá chất lượng môi trường.</Note>
      </Panel>
      <Panel title={<><Sparkles size={20}/> Diễn giải bằng Gemini</>} subtitle="Báo cáo tiếng Việt dựa trên thống kê Python của cả ba cụm">
        <div className="ce-ai-action"><p>Khám phá đặc điểm, sự khác biệt và mức độ đại diện của tâm cụm.</p>
          <button className="button button-primary" disabled={busy} onClick={analyze}><Sparkles size={16}/>{busy ? 'Đang phân tích…' : 'Phân tích bằng Gemini'}</button></div>
        {busy && <Loading text={`Gemini đang diễn giải cụm ${selected}…`}/>}
        {aiError && <ErrorBox message={aiError}/>}
        <div aria-live="polite">{report ? <article className="ce-report">
          <p className="ce-scope">Cụm {selected} · {reports[selected].model} · Nội dung AI cần được đối chiếu với bảng thống kê</p>
          <h3>Đặc điểm nổi bật</h3><p>{report.summary}</p>
          <h3>So sánh với hai cụm còn lại</h3><ul>{report.comparisons.map((v, i) => <li key={i}>{v}</li>)}</ul>
          <h3>Độ phân tán và tính đại diện</h3><p>{report.dispersion_and_representativeness}</p>
          <h3>Câu hỏi nghiên cứu tiếp theo</h3><ul>{report.research_questions.map((v, i) => <li key={i}>{v}</li>)}</ul>
          <h3>Hạn chế của kết quả</h3><ul>{report.limitations.map((v, i) => <li key={i}>{v}</li>)}</ul>
        </article> : !busy && <p className="ce-scope">Chưa có báo cáo cho cụm này. Nhấn nút để gửi thống kê tới Gemini.</p>}</div>
      </Panel>
      <Panel title="Phương pháp và giới hạn dữ liệu"><div className="ce-methodology">
        <p>K-Means K=3 dùng 7 tỷ trọng gốc, không scaling/PCA. Khoảng cách lưu sẵn đã được kiểm tra lại cho toàn bộ {num(stats.total_cities)} đô thị. Phân vị nội suy tuyến tính tại (n−1)×p.</p>
        {stats.methodology.notes.map((note) => <p key={note}>{note}</p>)}
      </div></Panel>
    </>}
  </div>;
}
