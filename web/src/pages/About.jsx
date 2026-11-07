import React from 'react';
import { ArrowRight, BarChart3, Database, Globe2, Layers3, Leaf, ShieldAlert, Sparkles } from 'lucide-react';
import { Note, Panel } from '../components/UI.jsx';

export default function About() {
  return <div className="page-enter">
    <div className="page-intro"><div><h1>Công nghệ dữ liệu cho đô thị bền vững</h1>
      <p>Hệ thống AI phân nhóm đô thị toàn cầu theo cơ cấu phát thải khí nhà kính và định hướng giải pháp công nghệ xanh phù hợp.</p></div></div>
    <div className="about-hero"><div className="about-hero-icon"><Leaf size={36}/></div>
      <div><h2>GreenSegment AI</h2><p>From emission profiles to informed green technology exploration.</p></div></div>
    <Panel title="Mục tiêu nghiên cứu"><div className="goal-grid">
      {[{Icon: Globe2, title:'Phân nhóm đô thị',text:'Nhận diện 3 kiểu cơ cấu phát thải trên tập đô thị toàn cầu.'},
        {Icon: BarChart3,title:'Giải thích đặc trưng',text:'Đọc tỷ trọng 7 lĩnh vực, so sánh đô thị với nhóm tham chiếu.'},
        {Icon: Sparkles,title:'Gợi ý bằng Gemini',text:'Đưa ra hướng công nghệ đáng nghiên cứu dựa trên dữ liệu và nguồn tham chiếu.'},
        {Icon: Layers3,title:'Trực quan tương tác',text:'Tra cứu, bản đồ thế giới, biểu đồ và hồ sơ cụm trên website.'}]
        .map(({Icon,title,text})=><div className="goal" key={title}><div className="goal-icon"><Icon size={22}/></div><h3>{title}</h3><p>{text}</p></div>)}
    </div></Panel>
    <Panel title="Quy trình hệ thống" subtitle="Mỗi giai đoạn dùng lại các dữ liệu và kết quả đã được xử lý trong dự án">
      <div className="pipeline">
        <div><Database size={24}/><strong>EDGAR + GHS-UCDB</strong><span>Dữ liệu phát thải và tọa độ</span></div>
        <ArrowRight size={20}/>
        <div><BarChart3 size={24}/><strong>7 tỷ trọng GHG</strong><span>Chuẩn hóa theo tổng đô thị</span></div>
        <ArrowRight size={20}/>
        <div><Layers3 size={24}/><strong>K-Means (K=3)</strong><span>Hồ sơ 3 cụm phát thải</span></div>
        <ArrowRight size={20}/>
        <div><Sparkles size={24}/><strong>Gemini Advisor</strong><span>Diễn giải và gợi ý giải pháp</span></div>
      </div>
    </Panel>
    <div className="about-cols">
      <Panel title="Nguồn dữ liệu"><p>Dữ liệu phát thải GHG năm 2024 từ <strong>EDGAR Cities</strong>; định danh đô thị được liên kết với <strong>GHS-UCDB</strong> để bổ sung tọa độ phục vụ bản đồ.</p>
        <p>Phân cụm được xây dựng trên <strong>7 tỷ trọng ngành</strong>: Nông nghiệp, Năng lượng, Công nghiệp, Quốc tế, Dân cư, Giao thông và Chất thải.</p></Panel>
      <Panel title="Phương pháp"><p>Sử dụng <strong>K-Means, K = 3</strong> làm mô hình phân cụm cuối cùng. Các đô thị được gán nhãn cụm từ tập dữ liệu đã xử lý; website chỉ đọc kết quả, <strong>không huấn luyện lại</strong> mô hình.</p>
        <p>Gemini dùng cơ cấu phát thải từng đô thị và thống kê cụm làm ngữ cảnh, sau đó chọn giải pháp từ danh mục tham chiếu đã biên soạn.</p></Panel>
    </div>
    <Panel title={<><ShieldAlert size={20}/> Phạm vi và giới hạn của kết quả</>}>
      <div className="limitations-list"><p>Phân cụm dựa trên <strong>cơ cấu</strong> phát thải, không phải xếp hạng đô thị tốt/xấu, không phải Scope 1/2/3.</p>
        <p>Tỷ trọng trung bình theo đô thị của một cụm <strong>không tương đương</strong> với tỷ trọng trên tổng phát thải cộng dồn của cụm.</p>
        <p>Đơn vị phát thải gốc từ EDGAR đang để nguyên và phải xác minh metadata trước khi quy đổi thành đơn vị cụ thể.</p>
        <p>Gợi ý công nghệ xanh chỉ là <strong>định hướng nghiên cứu sơ bộ</strong>, không chứng minh nhu cầu mua, mức giảm phát thải, ROI hoặc tính khả thi đầu tư tại một đô thị.</p></div>
    </Panel>
    <div className="about-footer">GreenSegment AI · Dữ liệu phát thải 2024 · Định danh đô thị 2025 · AI in Business</div>
  </div>;
}
