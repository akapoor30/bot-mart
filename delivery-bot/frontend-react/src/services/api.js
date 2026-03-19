// services/api.js — All API calls to FastAPI backend

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Helper: authHeaders injects the Keycloak access token into every request
const authHeaders = (token) => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${token}`,
});

// ── /compare ───────────────────────────────────────────────────────────────
export const comparePrices = async (item, pincode, token) => {
  const res = await fetch(`${BASE}/compare?item=${encodeURIComponent(item)}&pincode=${encodeURIComponent(pincode)}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Compare failed: ${res.status}`);
  return res.json();
};

// ── /cart ──────────────────────────────────────────────────────────────────
export const getCart = async (token) => {
  const res = await fetch(`${BASE}/cart/`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to load cart');
  return res.json();
};

export const addToCart = async (search_query, quantity = 1, token) => {
  const res = await fetch(`${BASE}/cart/add`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ search_query, quantity }),
  });
  if (!res.ok) throw new Error('Failed to add to cart');
  return res.json();
};

export const removeFromCart = async (itemId, token) => {
  const res = await fetch(`${BASE}/cart/${itemId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to remove item');
  return res.json();
};

export const clearCart = async (token) => {
  const res = await fetch(`${BASE}/cart/`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to clear cart');
  return res.json();
};

export const compareCartTotals = async (pincode, token) => {
  const res = await fetch(`${BASE}/cart/compare?pincode=${encodeURIComponent(pincode)}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Cart comparison failed');
  return res.json();
};

// ── /api/me ────────────────────────────────────────────────────────────────
export const syncMe = async (token) => {
  const res = await fetch(`${BASE}/api/me`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to sync user');
  return res.json();
};