import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { CLUSTER_COLORS } from '../constants.js';

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

export default function WorldMap({ points = [], onSelectCity, clusterOverlayRef }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const callbackRef = useRef(onSelectCity);
  callbackRef.current = onSelectCity;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { worldCopyJump: true, zoomControl: false, preferCanvas: true, minZoom: 2, maxZoom: 11 }).setView([19, 10], 2);
    L.control.zoom({ position: 'topright' }).addTo(map);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    // Fix map tile sizing after tab navigation/layout updates.
    const frame = requestAnimationFrame(() => map.invalidateSize());
    return () => { cancelAnimationFrame(frame); map.remove(); mapRef.current = null; layerRef.current = null; };
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    layer.clearLayers();
    const renderer = L.canvas({ padding: 0.5 });
    for (const point of points) {
      const color = CLUSTER_COLORS[point.cluster_id] || '#64748b';
      const circle = L.circleMarker([point.latitude, point.longitude], {
        radius: 3.2, color, fillColor: color, weight: 0.35, fillOpacity: 0.78,
        opacity: 0.9, renderer,
      });
      circle.bindTooltip(`<strong>${escapeHTML(point.city_name)}</strong><br/>${escapeHTML(point.country_name)} · Cụm ${point.cluster_id}`,
        { sticky: true, direction: 'top', opacity: 0.98 });
      circle.on('click', () => callbackRef.current?.(point.city_id));
      circle.addTo(layer);
    }
  }, [points]);

  return <div className="worldmap-wrap">
    <div className="worldmap" ref={containerRef} role="region" aria-label="Bản đồ các đô thị toàn cầu"/>
    {clusterOverlayRef && <div className="map-cluster-overlay" ref={clusterOverlayRef}/>}
    <div className="map-legend">
      <span><i style={{ background: CLUSTER_COLORS[0] }}/> Dân cư · Giao thông</span>
      <span><i style={{ background: CLUSTER_COLORS[1] }}/> Công nghiệp</span>
      <span><i style={{ background: CLUSTER_COLORS[2] }}/> Năng lượng</span>
    </div>
  </div>;
}
