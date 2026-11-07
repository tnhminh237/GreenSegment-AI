import React, { useEffect, useRef, useState } from 'react';
import { ArrowUpDown, Building2, Download, Globe2, Layers3, Search, Sparkles, Telescope } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts';
import { apiPost } from '../api.js';
import { CLUSTER_COLORS, SECTORS, SECTOR_LABELS, num, pct } from '../constants.js';
import { Empty, ErrorBox, Loading, Note, Panel } from '../components/UI.jsx';
import WorldMap from '../components/WorldMap.jsx';

const EXAMPLE = 'Tôi kinh doanh công nghệ thu hồi nhiệt thải công nghiệp. Hãy tìm 10 đô thị ở Nhật Bản có tỷ trọng phát thải công nghiệp từ 30% trở lên, ưu tiên đô thị có lượng GHG công nghiệp lớn nhất.';
const INITIAL_QUERY = { sector: 'industry', countries: [], cluster_id: null, min_sector_share_percent: null,
  max_sector_share_percent: null, sort_by: 'sector_emissions', sort_order: 'desc', limit: 10 };
const SORT_LABELS = { sector_share: 'Tỷ trọng lĩnh vực', sector_emissions: 'GHG lĩnh vực', total_ghg: 'Tổng GHG đô thị' };
const queryKey = (q) => JSON.stringify([q.sector, [...q.countries].sort(), q.cluster_id, q.min_sector_share_percent,
  q.max_sector_share_percent, q.sort_by, q.sort_order, q.limit]);

export default function MarketExplorer({ countries, onSelectCity }) {
  const [text, setText] = useState('');
  const [draft, setDraft] = useState(INITIAL_QUERY);
  const [parsed, setParsed] = useState(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [result, setResult] = useState(null);
  const [report, setReport] = useState(null);
  const [confirmedText, setConfirmedText] = useState('');
  const [busy, setBusy] = useState({});
  const [errors, setErrors] = useState({});
  const controllers = useRef({});
  useEffect(() => () => Object.values(controllers.current).forEach((c) => c.abort()), []);

  function stop(kind) {
    controllers.current[kind]?.abort();
    delete controllers.current[kind];
    setBusy((prev) => ({ ...prev, [kind]: false }));
  }
  async function run(kind, route, payload, onSuccess) {
    controllers.current[kind]?.abort();
    const controller = new AbortController();
    controllers.current[kind] = controller;
    setBusy((prev) => ({ ...prev, [kind]: true }));
    setErrors((prev) => ({ ...prev, [kind]: '' }));
    try {
      const response = await apiPost(route, payload, { signal: controller.signal });
      if (!controller.signal.aborted) onSuccess(response);
    } catch (e) { if (!controller.signal.aborted) setErrors((prev) => ({ ...prev, [kind]: e.message })); }
    finally { if (!controller.signal.aborted) setBusy((prev) => ({ ...prev, [kind]: false })); }
  }
  function edit(key, value) {
    stop('report'); stop('export'); setReport(null);
    setErrors((prev) => ({ ...prev, report: '', export: '', search: '' }));
    setDraft((prev) => ({ ...prev, [key]: value }));
  }
  function parse() {
    stop('report'); setReport(null);
    run('parse', '/market/parse', { text }, (response) => {
      setParsed(response); setDraft(response.query); setAcknowledged(false);
    });
  }
  function search(query = draft) {
    stop('report'); stop('export'); setReport(null);
    run('search', '/market/search', query, (response) => { setResult(response); setConfirmedText(text.trim()); });
  }
  function sort(field) {
    const next = { ...result.query, sort_by: field,
      sort_order: result.query.sort_by === field && result.query.sort_order === 'desc' ? 'asc' : 'desc' };
    setDraft(next); search(next);
  }
  function download(scope) {
    run('export', '/market/export', { query: result.query, scope }, (response) => {
      const url = URL.createObjectURL(new Blob([response.csv], { type: 'text/csv;charset=utf-8;' }));
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = response.filename;
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  const pending = busy.parse || busy.search;
  const stale = result && queryKey(result.query) !== queryKey(draft);
  const unsupported = parsed?.unsupported_criteria?.length > 0 && !acknowledged;
  const all = result?.matching_summary;
  const top = result?.top_summary;
  const sectorLabel = result && SECTOR_LABELS[result.query.sector];
  const clusterRows = all && [0, 1, 2].map((id) => ({ name: `Cụm ${id}`, count: all.cluster_counts[id], color: CLUSTER_COLORS[id] }));
  const rankRows = result?.items.map((city, i) => ({ ...city, label: `${i + 1}. ${city.city_name}`,
    value: result.query.sort_by === 'sector_share' ? city.sector_share_percent : result.query.sort_by === 'total_ghg' ? city.ghg_total_2024 : city.sector_emissions }));
  const rankValue = (v) => result.query.sort_by === 'sector_share' ? pct(v, 2) : num(v, 2);
  const reportFact = (key) => report?.verified_facts?.[key]?.display ?? '—';

  return <div className="page-enter market-explorer">
    <div className="page-intro"><div><div className="eyebrow">KHÁM PHÁ / NGHIÊN CỨU THỊ TRƯỜNG B2B</div>
      <h1>Market Explorer</h1><p>Sàng lọc đô thị từ dữ liệu phát thải để xác định phạm vi nghiên cứu thị trường công nghệ xanh.</p>
    </div><span className="year-pill"><Telescope size={16}/> EDGAR 2024 · K=3</span></div>
    <div className="market-steps"><span>01 · Hiểu yêu cầu</span><span>02 · Xác nhận tiêu chí</span><span>03 · Khám phá dữ liệu</span><span>04 · Tổng hợp nghiên cứu</span></div>
    <Panel title={<><Sparkles size={20}/> Yêu cầu nghiên cứu của doanh nghiệp</>} subtitle="Mô tả công nghệ, quốc gia và tiêu chí phát thải bạn muốn nghiên cứu">
      <label htmlFor="market-request" className="input-label">Nhập yêu cầu bằng tiếng Việt</label>
      <textarea id="market-request" rows={4} maxLength={4000} value={text} disabled={pending}
        onChange={(e) => setText(e.target.value)} placeholder={EXAMPLE}/>
      <div className="market-actions"><button className="button button-outline" disabled={pending} onClick={() => setText(EXAMPLE)}>Dùng yêu cầu mẫu</button>
        <button className="button button-primary" disabled={pending || text.trim().length < 5} onClick={parse}><Sparkles size={16}/>{busy.parse ? 'Đang phân tích…' : 'Phân tích yêu cầu'}</button></div>
      <p className="ce-scope">Có thể nhập bộ lọc trực tiếp bên dưới khi chưa dùng Gemini. Tên công nghệ chỉ giúp xác định lĩnh vực sơ bộ; không chứng minh nhu cầu mua.</p>
      {busy.parse && <Loading text="Gemini đang chuyển yêu cầu thành tiêu chí…"/>}{errors.parse && <ErrorBox message={errors.parse}/>}
      {parsed && <div className="market-interpretation"><strong>Cách hiểu sơ bộ · cần bạn kiểm tra</strong><p>{parsed.interpretation}</p><ul>{parsed.assumptions.map((v, i) => <li key={i}>{v}</li>)}</ul>
        {!!parsed.unsupported_criteria.length && <><ErrorBox message={`Chưa hỗ trợ: ${parsed.unsupported_criteria.join('; ')}`}/>
          <label className="market-ack"><input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)}/>Tôi đã chỉnh bộ lọc và đồng ý bỏ qua các yêu cầu chưa hỗ trợ.</label></>}
      </div>}
    </Panel>
    <Panel title={<><Search size={20}/> Kiểm tra và chỉnh tiêu chí</>} subtitle="Tìm trên toàn bộ 11.422 đô thị · Bộ lọc độc lập với sidebar">
      <form onSubmit={(e) => { e.preventDefault(); search(); }}>
        <fieldset disabled={pending} className="market-fields">
          <label>Lĩnh vực nghiên cứu<select id="market-sector" value={draft.sector} onChange={(e) => edit('sector', e.target.value)}>{SECTORS.map((s) => <option key={s} value={s}>{SECTOR_LABELS[s]}</option>)}</select></label>
          <label>Cụm K-Means<select id="market-cluster" value={draft.cluster_id ?? ''} onChange={(e) => edit('cluster_id', e.target.value === '' ? null : Number(e.target.value))}><option value="">Tất cả 3 cụm</option>{[0, 1, 2].map((id) => <option key={id} value={id}>Cụm {id}</option>)}</select></label>
          <label>Tỷ trọng tối thiểu (%)<input id="market-min" type="number" min="0" max="100" step="0.01" value={draft.min_sector_share_percent ?? ''} placeholder="Không giới hạn" onChange={(e) => edit('min_sector_share_percent', e.target.value === '' ? null : Number(e.target.value))}/></label>
          <label>Tỷ trọng tối đa (%)<input id="market-max" type="number" min="0" max="100" step="0.01" value={draft.max_sector_share_percent ?? ''} placeholder="Không giới hạn" onChange={(e) => edit('max_sector_share_percent', e.target.value === '' ? null : Number(e.target.value))}/></label>
          <label>Xếp theo<select id="market-sort" value={draft.sort_by} onChange={(e) => edit('sort_by', e.target.value)}>{Object.entries(SORT_LABELS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
          <label>Thứ tự<select id="market-order" value={draft.sort_order} onChange={(e) => edit('sort_order', e.target.value)}><option value="desc">Giảm dần</option><option value="asc">Tăng dần</option></select></label>
          <label>Số đô thị hiển thị<input id="market-limit" type="number" min="1" max="100" step="1" required value={draft.limit} onChange={(e) => edit('limit', e.target.value === '' ? '' : Number(e.target.value))}/></label>
          <div className="market-country-field"><label htmlFor="market-countries">Quốc gia / vùng lãnh thổ (chọn nhiều)</label><select id="market-countries" multiple size={5} value={draft.countries} onChange={(e) => edit('countries', Array.from(e.target.selectedOptions, (option) => option.value))}>{countries.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}</select>
            <button type="button" className="market-text-button" onClick={() => edit('countries', [])}>Chọn toàn bộ quốc gia</button><small>Ctrl/Cmd + nhấn để chọn nhiều trên desktop. Không chọn riêng quốc gia nào = toàn bộ dữ liệu.</small></div>
        </fieldset>
        <p className="ce-scope">Phạm vi: {draft.countries.length ? draft.countries.join(', ') : 'Tất cả quốc gia'}. Ngưỡng để trống nghĩa là không lọc theo ngưỡng. Mặc định ban đầu: Công nghiệp, GHG lĩnh vực giảm dần, Top 10.</p>
        <Note>Chưa hỗ trợ chọn châu lục vì chưa có bảng quốc gia–khu vực đã kiểm tra. Dữ liệu phát thải không xác nhận nhu cầu thị trường.</Note>
        <button type="submit" className="button button-primary" disabled={pending || unsupported}><Search size={16}/>{busy.search ? 'Đang truy vấn…' : 'Xác nhận bộ lọc và tìm kiếm'}</button>
      </form>
      {errors.search && <ErrorBox message={errors.search}/>}{busy.search && <Loading text="Python đang lọc và xếp hạng toàn bộ tập phù hợp…"/>}
    </Panel>
    {result && <div className="market-results" aria-live="polite">
      {stale && <Note>Tiêu chí đã thay đổi. Các kết quả bên dưới thuộc bộ lọc đã chạy trước đó; xác nhận tìm kiếm lại trước khi xuất CSV hoặc tạo báo cáo.</Note>}
      <div className="market-result-heading"><div><div className="eyebrow">KẾT QUẢ ĐÃ XÁC NHẬN · {sectorLabel?.toUpperCase()}</div><h2>Phạm vi nghiên cứu từ dữ liệu phát thải</h2></div><span className="year-pill">{SORT_LABELS[result.query.sort_by]} · {result.query.sort_order === 'desc' ? 'Giảm dần' : 'Tăng dần'}</span></div>
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-icon green"><Building2 size={23}/></div><span>Toàn bộ đô thị phù hợp</span><strong>{num(all.city_count)}</strong><small>Trong {num(result.source_city_count)} đô thị</small></div>
        <div className="stat-card"><div className="stat-icon blue"><Globe2 size={23}/></div><span>Quốc gia trong tập phù hợp</span><strong>{num(all.country_count)}</strong><small>Tính trên toàn bộ kết quả</small></div>
        <div className="stat-card"><div className="stat-icon orange"><Layers3 size={23}/></div><span>Tỷ trọng trung bình</span><strong>{all.mean_sector_share_percent == null ? '—' : pct(all.mean_sector_share_percent, 2)}</strong><small>{sectorLabel} · toàn bộ tập phù hợp</small></div>
        <div className="stat-card"><div className="stat-icon purple"><Building2 size={23}/></div><span>Top N đang hiển thị</span><strong>{num(top.city_count)}</strong><small>Giới hạn được chọn: {result.query.limit}</small></div>
      </div>
      <p className="market-top-summary">Riêng Top N: {num(top.country_count)} quốc gia · Tỷ trọng trung bình {top.mean_sector_share_percent == null ? '—' : pct(top.mean_sector_share_percent, 2)} · {[0, 1, 2].map((id) => `Cụm ${id}: ${num(top.cluster_counts[id])}`).join(' · ')}.</p>
      {!all.city_count ? <Panel><Empty>Không có đô thị đáp ứng tiêu chí. Hãy điều chỉnh quốc gia, cụm hoặc ngưỡng tỷ trọng rồi tìm kiếm lại.</Empty></Panel> : <>
        <Panel title={`Danh sách ${top.city_count} đô thị đang hiển thị`} subtitle={`${sectorLabel} · Thứ tự theo dữ liệu phát thải, không phải mức hấp dẫn thương mại`}
          action={<div className="market-actions"><button className="button button-outline" disabled={stale || busy.export || pending} onClick={() => download('top')}><Download size={15}/> CSV Top N</button><button className="button button-outline" disabled={stale || busy.export || pending} onClick={() => download('matching')}>CSV toàn bộ ({num(all.city_count)})</button></div>}>
          <div className="ce-table-scroll market-table-scroll"><table className="ce-table market-table"><thead><tr>
            <th scope="col">Đô thị</th><th scope="col">Quốc gia</th><th scope="col">Cụm</th>
            {[['sector_share', 'Tỷ trọng (%)'], ['sector_emissions', 'GHG lĩnh vực'], ['total_ghg', 'Tổng GHG']].map(([key, label]) => <th scope="col" key={key} aria-sort={result.query.sort_by === key ? result.query.sort_order === 'asc' ? 'ascending' : 'descending' : 'none'}><button type="button" disabled={stale || pending} onClick={() => sort(key)}>{label}<ArrowUpDown size={12}/></button></th>)}<th scope="col">Hồ sơ</th>
          </tr></thead><tbody>{result.items.map((city) => <tr key={city.city_id}><th scope="row">{city.city_name}</th><td>{city.country_name}</td><td><span className="market-cluster-dot" style={{ background: CLUSTER_COLORS[city.cluster_id] }}/>{city.cluster_id}</td><td>{pct(city.sector_share_percent, 2)}</td><td>{num(city.sector_emissions, 2)}</td><td>{num(city.ghg_total_2024, 2)}</td><td><button className="market-text-button" onClick={() => onSelectCity(city.city_id)}>Mở hồ sơ</button></td></tr>)}</tbody></table></div>
          <p className="ce-scope">Có thể cuộn ngang bảng trên màn hình nhỏ. Nhấn tiêu đề cột số liệu để xếp lại toàn bộ tập phù hợp rồi lấy Top N.</p>
          {errors.export && <ErrorBox message={errors.export}/>}{busy.export && <Loading text="Đang chuẩn bị CSV từ dữ liệu thật…"/>}<Note>{result.units_note}</Note>
        </Panel>
        <div className="market-visuals">
          <Panel title="Bản đồ tập đô thị phù hợp" subtitle="Nhấn một điểm để mở hồ sơ City Explorer"><WorldMap points={result.map.points} onSelectCity={onSelectCity}/><p className="map-caption">Hiển thị {num(result.map.shown)} / {num(result.map.total_matching)} đô thị phù hợp{result.map.sampled ? ' (lấy mẫu đều tối đa 5.000 điểm)' : ''}; {num(result.map.valid_coordinates)} đô thị có tọa độ hợp lệ. Nền bản đồ cần Internet.</p></Panel>
          <Panel title="Phân bố theo cụm K-Means" subtitle="Toàn bộ tập phù hợp, không chỉ Top N"><div className="market-cluster-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={clusterRows} margin={{ left: 0, right: 15, top: 8, bottom: 8 }}><CartesianGrid vertical={false} strokeDasharray="3 5"/><XAxis dataKey="name" tick={{ fontSize: 12 }}/><YAxis allowDecimals={false} tick={{ fontSize: 11 }}/><Tooltip formatter={(v) => [num(v), 'Đô thị']}/><Bar dataKey="count" maxBarSize={55} radius={[6, 6, 0, 0]}>{clusterRows.map((row) => <Cell key={row.name} fill={row.color}/>)}</Bar></BarChart></ResponsiveContainer></div><div className="market-cluster-counts">{clusterRows.map((row) => <span key={row.name}>{row.name}: <strong>{num(row.count)}</strong></span>)}</div></Panel>
        </div>
        <Panel title={`So sánh Top ${top.city_count} theo ${SORT_LABELS[result.query.sort_by].toLowerCase()}`} subtitle={result.query.sort_by === 'sector_share' ? 'Đơn vị % · Không phải điểm tiềm năng' : 'Đơn vị GHG gốc EDGAR chưa xác minh'}>
          <div className="market-ranking-scroll"><div style={{ height: Math.max(260, rankRows.length * 32) }}><ResponsiveContainer width="100%" height="100%"><BarChart data={rankRows} layout="vertical" margin={{ left: 0, right: 20, top: 8, bottom: 8 }}><CartesianGrid horizontal={false} strokeDasharray="3 5"/><XAxis type="number" tickFormatter={(v) => result.query.sort_by === 'sector_share' ? pct(v, 0) : num(v)} tick={{ fontSize: 10 }}/><YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 11 }} tickFormatter={(label) => label.length > 22 ? `${label.slice(0, 21)}…` : label}/><Tooltip formatter={(v) => [rankValue(v), SORT_LABELS[result.query.sort_by]]} labelFormatter={(_, payload) => payload?.[0]?.payload ? `${payload[0].payload.city_name} · ${payload[0].payload.country_name}` : ''}/><Bar dataKey="value" maxBarSize={19} radius={[0, 4, 4, 0]} fill="#087e67"/></BarChart></ResponsiveContainer></div></div>
        </Panel>
        <Panel title={<><Sparkles size={20}/> Báo cáo nghiên cứu thị trường bằng Gemini</>} subtitle="Mục tiêu 300–450 từ · Ưu tiên dữ liệu đúng và nội dung đầy đủ">
          <div className="ce-ai-action"><p>Báo cáo gắn với bộ lọc đã xác nhận và phân biệt toàn bộ tập phù hợp với Top N.</p><button className="button button-primary" disabled={stale || pending || busy.report} onClick={() => run('report', '/market/report', { query: result.query, business_request: confirmedText }, setReport)}><Sparkles size={16}/>{busy.report ? 'Đang tạo báo cáo…' : 'Tạo báo cáo thị trường bằng Gemini'}</button></div>
          {busy.report && <Loading text="Gemini đang tổng hợp dữ liệu nghiên cứu…"/>}{errors.report && <ErrorBox message={errors.report}/>}
          <div aria-live="polite">{report ? <article className="ce-report"><p className="ce-scope">{report.model} · Nội dung AI cần đối chiếu số liệu và nghiên cứu bổ sung</p>
            {report.verified_facts && <><h3>Số liệu Python đã kiểm chứng</h3><div className="ce-table-scroll"><table className="ce-table market-report-facts"><thead><tr><th scope="col">Phạm vi</th><th scope="col">Đô thị</th><th scope="col">Quốc gia</th><th scope="col">Tỷ trọng TB</th>{[0, 1, 2].map((id) => <th key={id} scope="col">Cụm {id}</th>)}</tr></thead>
              <tbody>{[['matching', 'Toàn bộ tập phù hợp'], ['top', 'Top N hiển thị']].map(([scope, label]) => <tr key={scope}><th scope="row">{label}</th><td>{reportFact(`${scope}.city_count`)}</td><td>{reportFact(`${scope}.country_count`)}</td><td>{reportFact(`${scope}.mean_sector_share_percent`)}</td>{[0, 1, 2].map((id) => <td key={id}>{reportFact(`${scope}.clusters.${id}.city_count`)} ({reportFact(`${scope}.clusters.${id}.city_percentage`)})</td>)}</tr>)}</tbody></table></div><p className="ce-scope">Các số trong bảng được Python gắn trực tiếp từ dữ liệu EDGAR {reportFact('dataset.year')}, không do Gemini tự chép lại.</p></>}
            <h3>Yêu cầu và phạm vi nghiên cứu</h3><p>{report.report.research_request}</p><h3>Đặc điểm phát thải</h3><p>{report.report.emissions_profile}</p><h3>Phân bố theo cụm</h3><p>{report.report.cluster_distribution}</p>
            <h3>Một số đô thị trong Top N</h3>{report.report.city_comparisons.map((city, i) => { const source = report.representative_cities.find((c) => c.city_id === city.city_id); return <div key={i}><strong>{source?.city_name} · {source?.country_name}</strong>{report.verified_facts && <p className="ce-scope">Thứ hạng {reportFact(`cities.${city.city_id}.rank`)} · Cụm {reportFact(`cities.${city.city_id}.cluster_id`)} · Tỷ trọng {reportFact(`cities.${city.city_id}.sector_share_percent`)} · Chênh lệch với trung bình toàn bộ tập phù hợp: {reportFact(`cities.${city.city_id}.share_gap_matching_pp`)}</p>}<p>{city.text}</p></div>; })}
            <h3>Liên hệ công nghệ sơ bộ</h3><p>{report.report.preliminary_technology_link}</p><h3>Thông tin cần bổ sung</h3><ul>{report.report.additional_information.map((v, i) => <li key={i}>{v}</li>)}</ul><h3>Giới hạn kết luận</h3><p>{report.report.limitations}</p>
          </article> : !busy.report && <p className="ce-scope">Chưa tạo báo cáo cho kết quả này. Báo cáo không dự đoán doanh số hoặc khẳng định nhu cầu mua công nghệ.</p>}</div>
        </Panel>
      </>}
    </div>}
  </div>;
}
