import React, { useEffect, useState } from 'react';
import { ArrowRight, BookOpen, CheckCircle2, ChevronDown, Leaf, Lightbulb, MapPin, Search, ShieldAlert, Sparkles } from 'lucide-react';
import { apiGet, apiPost } from '../api.js';
import { SECTOR_LABELS, num, pct } from '../constants.js';
import { Empty, ErrorBox, ExternalLink, Loading, Note, Panel, Success } from '../components/UI.jsx';

export default function GreenAdvisor({ selectedCityId, onSelectCity }) {
  const [mode, setMode] = useState('city');
  const [clusterId, setClusterId] = useState('1');
  const [search, setSearch] = useState('Nagoya');
  const [searchResults, setSearchResults] = useState([]);
  const [city, setCity] = useState(null);
  const [output, setOutput] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showCandidates, setShowCandidates] = useState(false);

  useEffect(() => {
    if (!selectedCityId) return;
    const controller = new AbortController();
    apiGet(`/cities/${encodeURIComponent(selectedCityId)}`, {}, { signal: controller.signal })
      .then((row) => { setCity(row); setSearch(row.city_name); })
      .catch(() => {});
    return () => controller.abort();
  }, [selectedCityId]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => apiGet('/cities', { search, page_size: 7 }, { signal: controller.signal })
      .then((list) => {
        setSearchResults(list.items || []);
        if (!selectedCityId && search.trim().toLowerCase() === 'nagoya') {
          const nagoya = list.items?.find((x) => x.city_name.toLowerCase() === 'nagoya' && x.country_name === 'Japan');
          if (nagoya) onSelectCity(nagoya.city_id);
        }
      }).catch(() => {}), 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [search]);

  const payload = mode === 'city'
    ? { mode: 'city', city_id: selectedCityId }
    : { mode: 'cluster', cluster_id: Number(clusterId) };

  async function run(dryRun = false) {
    if (mode === 'city' && !selectedCityId) { setError('Hãy chọn một đô thị trước.'); return; }
    setError(''); setOutput(null); setPreview(null); setLoading(true);
    try {
      const response = await apiPost(dryRun ? '/advisor/preview' : '/advisor', payload);
      if (dryRun) setPreview(response); else setOutput(response);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return <div className="page-enter">
    <div className="page-intro"><div><div className="eyebrow">AI ADVISOR / GIẢI PHÁP</div><h1>Định hướng công nghệ xanh với Gemini</h1>
      <p>Kết hợp hồ sơ phát thải EDGAR, nhóm tham chiếu K-Means và danh mục công nghệ xanh có nguồn.</p></div>
      <span className="ai-pill"><Sparkles size={15}/> Powered by Gemini</span>
    </div>
    <Panel title={<><Sparkles size={20}/> Thiết lập phân tích</>} subtitle="Gemini chọn giải pháp phù hợp về mặt lĩnh vực; không dự đoán khả năng mua hoặc triển khai">
      <div className="mode-switch"><button className={mode === 'city' ? 'active' : ''} type="button" onClick={() => { setMode('city'); setOutput(null); setPreview(null); }}>
        <MapPin size={16}/> Theo đô thị</button><button className={mode === 'cluster' ? 'active' : ''} type="button"
        onClick={() => { setMode('cluster'); setOutput(null); setPreview(null); }}><Leaf size={16}/> Theo cụm</button></div>
      <div className="advisor-form">
        {mode === 'city' ? <div className="advisor-city-picker">
          <label className="input-label">Chọn đô thị</label>
          <div className="search-input-wrap"><Search size={17}/><input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm đô thị..." aria-label="Tìm đô thị để nhận gợi ý"/></div>
          {searchResults.length > 0 && <div className="advisor-search-results">
            {searchResults.map((item) => <button type="button" key={item.city_id} className={item.city_id === selectedCityId ? 'chosen' : ''}
              onClick={() => { onSelectCity(item.city_id); setSearch(item.city_name); }}>
              <span>{item.city_name}<small>{item.country_name} · Cụm {item.cluster_id}</small></span>
              {item.city_id === selectedCityId && <CheckCircle2 size={16}/>}</button>)}
          </div>}
          {selectedCityId && city && <div className="chosen-city"><CheckCircle2 size={16}/> Đã chọn: <strong>{city.city_name}, {city.country_name}</strong> · Cụm {city.cluster_id}</div>}
        </div> : <div className="advisor-cluster-picker"><label className="input-label" htmlFor="advisor-cluster">Chọn nhóm đô thị</label>
          <select id="advisor-cluster" value={clusterId} onChange={(e) => setClusterId(e.target.value)}>
            <option value="0">Cụm 0 — Dân cư · Giao thông</option>
            <option value="1">Cụm 1 — Công nghiệp</option>
            <option value="2">Cụm 2 — Năng lượng</option>
          </select><p className="helper-text">Gợi ý ở cấp cụm là định hướng chung, không tự động áp dụng cho tất cả đô thị.</p></div>}
      </div>
      <div className="advisor-actions"><button type="button" className="button button-primary"
        disabled={loading || (mode === 'city' && !selectedCityId)} onClick={() => run(false)}>
        <Sparkles size={17}/>{loading ? 'Đang xử lý...' : 'Phân tích bằng Gemini'}<ArrowRight size={16}/></button>
        <button type="button" className="button button-outline" disabled={loading || (mode === 'city' && !selectedCityId)} onClick={() => run(true)}>
          <BookOpen size={16}/> Xem dữ liệu đầu vào (không gọi AI)</button></div>
    </Panel>
    {error && <ErrorBox message={error}/>} 
    {loading && <Panel><Loading text="Đang chuẩn bị dữ liệu và xử lý yêu cầu... Có thể mất một lúc nếu Gemini đang bận."/></Panel>}
    {preview && <Panel title="Dữ liệu gửi tới Gemini" subtitle="Chế độ xem trước — không gọi API và không sử dụng quota">
      <Success>Đọc dữ liệu thành công. Tìm được {preview.catalog_solutions?.length || 0} giải pháp ứng viên từ danh mục.</Success>
      <div className="candidate-list">{preview.catalog_solutions?.map((s) => <span key={s.solution_id}>{s.solution_id} · {s.name_vi}</span>)}</div>
      <details className="raw-preview"><summary>Xem JSON đầu vào</summary><pre>{JSON.stringify(preview.input, null, 2)}</pre></details>
    </Panel>}
    {!loading && !output && !preview && !error && <div className="advisor-empty"><div className="advisor-orb"><Sparkles size={34}/></div>
      <h2>Khám phá giải pháp xanh dựa trên dữ liệu</h2><p>Chọn đô thị hoặc cụm, sau đó bấm “Phân tích bằng Gemini” để nhận phân tích có dẫn nguồn và điều kiện áp dụng.</p>
      <div className="advisor-steps"><span>01 · EDGAR 2024</span><ArrowRight size={16}/><span>02 · K-Means</span><ArrowRight size={16}/><span>03 · Gemini</span></div></div>}
    {output?.advisor && <div className="advisor-result">
      <Panel title={<><CheckCircle2 size={20}/> Phân tích đã hoàn tất</>} subtitle={`Mô hình: ${output.model} · ${output.input?.mode === 'city' ? 'Theo đô thị' : 'Theo cụm'}`}>
        <p className="advisor-summary">{output.advisor.summary_vi}</p>
        <div className="advisor-context"><strong>Ngữ cảnh K-Means</strong><p>{output.advisor.cluster_context_vi}</p>
          {output.advisor.city_cluster_comparison_vi && <p>{output.advisor.city_cluster_comparison_vi}</p>}</div>
        <h3 className="subheading">Diễn giải cơ cấu phát thải</h3><p className="interpretation">{output.advisor.interpretation_vi}</p>
      </Panel>
      <div className="solutions-title"><div><div className="eyebrow">GREEN TECHNOLOGY CATALOG</div><h2>Giải pháp đáng nghiên cứu</h2>
        <p>{output.advisor.recommended_solutions?.length || 0} giải pháp được Gemini lựa chọn từ danh mục tham chiếu.</p></div></div>
      <div className="solution-grid">
        {output.advisor.recommended_solutions?.map((s) => <article className="solution-card" key={s.solution_id}>
          <div className="solution-top"><span className="solution-id">{s.solution_id}</span><span className="solution-sector">{SECTOR_LABELS[s.edgar_sector?.toLowerCase()] || s.edgar_sector}</span></div>
          <div className="solution-icon"><Lightbulb size={23}/></div><h3>{s.solution_name_vi}</h3><p>{s.reason_vi}</p>
          <div className="solution-section"><strong>Dữ liệu địa phương cần xác minh</strong><ul>{s.required_local_data_vi?.map((text, i) => <li key={i}>{text}</li>)}</ul></div>
          {!!s.additional_local_data_needed_vi?.length && <div className="solution-section"><strong>Gemini đề xuất kiểm tra thêm</strong>
            <ul>{s.additional_local_data_needed_vi.map((text, i) => <li key={i}>{text}</li>)}</ul></div>}
          <div className="solution-limit"><ShieldAlert size={15}/><span>{s.limitations_from_catalog_vi}</span></div>
          <div className="solution-sources"><strong>Nguồn tham chiếu từ danh mục</strong>
            {s.evidence_from_catalog?.map((source, i) => <ExternalLink key={i} url={source.url}>{source.organization} · {source.title}</ExternalLink>)}
          </div>
        </article>)}
      </div>
      <Panel title="Giới hạn của khuyến nghị"><Note>{output.advisor.limitations_vi}</Note><p className="disclaimer">{output.advisor.disclaimer}</p></Panel>
    </div>}
  </div>;
}
