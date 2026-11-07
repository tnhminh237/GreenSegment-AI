import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell } from 'recharts';
import { SECTORS, SECTOR_LABELS, SECTOR_COLORS, pct, num } from '../constants.js';

export function ClusterStackedChart({ clusters, filtered = false }) {
  const rows = clusters.map((c) => ({
    cluster: `Cụm ${c.cluster_id}`,
    ...Object.fromEntries(SECTORS.map((s) => [s, (filtered ? c.filtered_mean_sector_shares_percent : c.mean_sector_shares_percent)?.[s] || 0])),
  }));
  return <div className="chart-wrap stacked-chart">
    <div className="stacked-plot"><ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 12, bottom: 2, left: 8 }} barCategoryGap={19}>
        <CartesianGrid strokeDasharray="3 6" horizontal={false} stroke="#edf1f2" />
        <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => pct(v, 0)} tick={{ fontSize: 11, fill: '#72838a' }} />
        <YAxis dataKey="cluster" type="category" tick={{ fontSize: 12, fill: '#34575c' }} width={65} axisLine={false} tickLine={false} />
        <Tooltip formatter={(v, name) => [pct(v, 2), SECTOR_LABELS[name] || name]} />
        {SECTORS.map((s, i) => <Bar key={s} dataKey={s} name={SECTOR_LABELS[s]} stackId="sectors" fill={SECTOR_COLORS[s]}
          radius={i === SECTORS.length - 1 ? [0, 5, 5, 0] : undefined} maxBarSize={34}/>) }
      </BarChart>
    </ResponsiveContainer></div>
    <div className="sector-legend">{SECTORS.map((s) => <span key={s}><i style={{ background: SECTOR_COLORS[s] }} />{SECTOR_LABELS[s]}</span>)}</div>
  </div>;
}

export function CitySectorChart({ shares, clusterMeans }) {
  const rows = SECTORS.map((s) => ({ name: SECTOR_LABELS[s], city: shares?.[s] || 0, cluster: clusterMeans?.[s] || 0 }));
  return <div className="chart-wrap city-sector-chart">
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 25, bottom: 6, left: 10 }}>
        <CartesianGrid stroke="#edf1f2" horizontal={false} strokeDasharray="3 5"/>
        <XAxis type="number" tickFormatter={(n) => `${n}%`} domain={[0, 'auto']} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="name" width={85} tick={{ fontSize: 11, fill: '#426168' }} axisLine={false} tickLine={false}/>
        <Tooltip formatter={(v, n) => [pct(v, 2), n === 'city' ? 'Đô thị' : 'Trung bình cụm']} />
        <Legend formatter={(name) => name === 'city' ? 'Đô thị' : 'Trung bình cụm'} verticalAlign="top" height={28} />
        <Bar dataKey="city" fill="#087f68" maxBarSize={15} radius={[0, 4, 4, 0]}/>
        <Bar dataKey="cluster" fill="#b9dcd0" maxBarSize={15} radius={[0, 4, 4, 0]}/>
      </BarChart>
    </ResponsiveContainer>
  </div>;
}

export function SectorProgress({ shares }) {
  return <div className="sector-progress-list">
    {SECTORS.map((s) => <div className="sector-progress-row" key={s}>
      <span className="sector-progress-label"><i style={{ backgroundColor: SECTOR_COLORS[s] }} />{SECTOR_LABELS[s]}</span>
      <div className="progress-track"><div style={{ background: SECTOR_COLORS[s], width: `${Math.min(100, Math.max(0, shares?.[s] ?? 0))}%` }}/></div>
      <strong>{pct(shares?.[s], 1)}</strong>
    </div>)}
  </div>;
}
