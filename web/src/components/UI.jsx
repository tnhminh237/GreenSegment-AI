import React from 'react';
import { AlertTriangle, ArrowUpRight, CheckCircle2, LoaderCircle } from 'lucide-react';

export function Panel({ title, subtitle, action, children, className = '' }) {
  return <section className={`panel ${className}`}>
    {(title || action) && <header className="panel-heading">
      <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
      {action}
    </header>}
    {children}
  </section>;
}

export function Loading({ text = 'Đang tải dữ liệu...' }) {
  return <div className="loading"><LoaderCircle className="spin" size={20} />{text}</div>;
}

export function ErrorBox({ message }) {
  return <div role="alert" className="error-box"><AlertTriangle size={18} /><span>{message}</span></div>;
}

export function Note({ children }) {
  return <p className="data-note"><AlertTriangle size={15} />{children}</p>;
}

export function Empty({ children }) {
  return <div className="empty-state">{children || 'Không có dữ liệu phù hợp.'}</div>;
}

export function Success({ children }) {
  return <div className="success-box"><CheckCircle2 size={18} />{children}</div>;
}

export function ExternalLink({ url, children }) {
  try {
    if (!url || !['https:', 'http:'].includes(new URL(url).protocol)) return null;
  } catch { return null; }
  return <a href={url} target="_blank" rel="noreferrer noopener" className="source-link">
    {children}<ArrowUpRight size={14} aria-hidden="true" />
  </a>;
}
