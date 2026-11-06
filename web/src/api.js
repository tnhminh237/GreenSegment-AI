export async function apiGet(route, params = {}, options = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  }
  const url = `/api${route}${query.size ? `?${query}` : ''}`;
  return fetchJson(url, options);
}

export async function apiPost(route, payload, options = {}) {
  return fetchJson(`/api${route}`, {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    body: JSON.stringify(payload),
  });
}

async function fetchJson(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error('Không kết nối được backend. Hãy chạy FastAPI tại localhost:8000.');
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item) => item.msg).join('; ')
      : `Máy chủ trả về HTTP ${response.status}.`;
    throw new Error(message);
  }
  return body;
}
