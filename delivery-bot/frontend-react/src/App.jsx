import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from 'react-oidc-context';
import './App.css';
import {
  comparePrices,
  getCart,
  addToCart,
  removeFromCart,
  clearCart,
  compareCartTotals,
  syncMe,
} from './services/api';

const cap = (str) => str ? str.replace(/\b\w/g, c => c.toUpperCase()) : str;

// ── Store badge ──────────────────────────────────────────────────────────────
function StoreBadge({ store, cheapest }) {
  const cls = `store-badge badge-${(store || 'unknown').toLowerCase()}`;
  return (
    <>
      <span className={cls}>{store || 'Unknown'}</span>
      {cheapest && <span className="store-badge badge-cheapest">🏆 Best Total</span>}
    </>
  );
}

// ── AI mismatch badge ────────────────────────────────────────────────────────
function MismatchBadge({ reason }) {
  const [show, setShow] = useState(false);
  return (
    <span
      className="mismatch-badge"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      ⚠ Different variant
      {show && reason && (
        <span className="mismatch-tooltip">{reason}</span>
      )}
    </span>
  );
}

// ── Fee row helper ───────────────────────────────────────────────────────────
function FeeRow({ label, value }) {
  if (!value || value === 0) return null;
  return (
    <div className="fee-row">
      <span>{label}</span>
      <span>₹{value}</span>
    </div>
  );
}

// ── Single result card ───────────────────────────────────────────────────────
function ResultCard({ item, isCheapestTotal, token, searchQuery, cart, refreshCart }) {
  const [updating, setUpdating] = useState(false);

  // find in cart
  const cartItem = cart.find(c => c.search_query.toLowerCase() === searchQuery.toLowerCase());
  const quantity = cartItem ? cartItem.quantity : 0;

  const handleUpdate = async (delta) => {
    setUpdating(true);
    try {
      await addToCart(searchQuery, delta, token, item.name, item.store.toLowerCase());
      await refreshCart();
    } catch (e) { console.error(e); }
    finally { setUpdating(false); }
  };

  if (item.status !== 'success') {
    return (
      <div className="result-card failed">
        <StoreBadge store={item.store} />
        <p className="card-error">{item.error || 'Scrape failed'}</p>
      </div>
    );
  }

  const isMismatch = item.ai_match === false;
  const totalPrice = item.total_price ?? (
    (item.price || 0) + (item.delivery_fee || 0) +
    (item.handling_fee || 0) + (item.platform_fee || 0) + (item.gst_fee || 0)
  );

  return (
    <div className={`result-card ${isCheapestTotal ? 'cheapest' : ''} ${isMismatch ? 'mismatched' : ''}`}>
      <div className="card-badges">
        <StoreBadge store={item.store} cheapest={isCheapestTotal} />
        {isMismatch && <MismatchBadge reason={item.ai_mismatch_reason} />}
      </div>

      <p className="card-name">{item.name}</p>

      <div className="card-price-block">
        <div className="card-total-price">
          <span className="total-label">Total</span>
          <span className="total-value"><sup>₹</sup>{totalPrice}</span>
        </div>
        <div className="card-item-price">Item ₹{item.price}</div>
      </div>

      {(item.delivery_fee > 0 || item.handling_fee > 0 || item.platform_fee > 0 || item.gst_fee > 0) && (
        <div className="card-fees">
          <FeeRow label="Delivery"  value={item.delivery_fee} />
          <FeeRow label="Handling"  value={item.handling_fee} />
          <FeeRow label="Platform"  value={item.platform_fee} />
          <FeeRow label="GST"       value={item.gst_fee} />
        </div>
      )}

      <div className="card-footer">
        {quantity > 0 ? (
          <div className="qty-selector">
            <button className="btn-qty" onClick={() => handleUpdate(-1)} disabled={updating}>-</button>
            <span className="qty-value">{updating ? '…' : quantity}</span>
            <button className="btn-qty" onClick={() => handleUpdate(1)} disabled={updating}>+</button>
          </div>
        ) : (
          <button className="btn btn-cart" onClick={() => handleUpdate(1)} disabled={updating}>
            {updating ? 'Adding…' : '+ Cart'}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Cart Panel ───────────────────────────────────────────────────────────────
function CartPanel({ token, cart, refreshCart, pincode }) {
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing]   = useState(false);
  const [clearing, setClearing]     = useState(false);
  const [updatingId, setUpdatingId] = useState(null);

  const handleUpdate = async (searchQuery, delta, id) => {
    setUpdatingId(id);
    try {
      await addToCart(searchQuery, delta, token);
      await refreshCart();
      if (delta < 0 && cart.find(c => c.id === id)?.quantity <= 1) {
        setComparison(null);
      }
    } catch (e) { console.error(e); } finally { setUpdatingId(null); }
  };

  const handleClear = async () => {
    setClearing(true);
    try {
      await clearCart(token);
      await refreshCart();
      setComparison(null);
    } catch (e) { console.error(e); } finally { setClearing(false); }
  };

  const handleCompare = async () => {
    setComparing(true);
    setComparison(null);
    try {
      const data = await compareCartTotals(pincode || '560095', token);
      setComparison(data);
    } catch (e) { console.error(e); } finally { setComparing(false); }
  };

  return (
    <aside className="cart-panel">
      <div className="cart-header">
        <h3>🛒 My Cart <span className="cart-count">{cart.length}</span></h3>
        {cart.length > 0 && (
          <button className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.3rem 0.7rem' }}
            onClick={handleClear} disabled={clearing}>
            {clearing ? '…' : 'Clear'}
          </button>
        )}
      </div>

      <div className="cart-body">
        {cart.length === 0 && (
          <p className="cart-empty">Your cart is empty.<br />Search for a product and add items.</p>
        )}
        {cart.map(item => (
          <div className="cart-item" key={item.id}>
            <div className="cart-item-details">
              <span className="cart-item-name">{cap(item.search_query)}</span>
              {item.product_name && (
                <span className="cart-item-variant">
                  {item.product_name} <span className="cart-item-plat">({cap(item.preferred_platform) || 'Any'})</span>
                </span>
              )}
            </div>
            <div className="cart-qty-selector">
              <button 
                onClick={() => handleUpdate(item.search_query, -1, item.id)} 
                disabled={updatingId === item.id}
                className="btn-qty-small"
              >-</button>
              <span className="qty-value">{updatingId === item.id ? '…' : item.quantity}</span>
              <button 
                onClick={() => handleUpdate(item.search_query, 1, item.id)} 
                disabled={updatingId === item.id}
                className="btn-qty-small"
              >+</button>
            </div>
          </div>
        ))}

        {comparison && (
          <div className="comparison">
            <h4 style={{ fontSize: '0.85rem', color: 'var(--muted)', marginBottom: '0.5rem' }}>
              {comparison.cheapest_platform
                ? `🏆 Best: ${cap(comparison.cheapest_platform)}${comparison.you_save ? ` — Save ₹${comparison.you_save}` : ''}`
                : 'No complete results'}
            </h4>
            {(comparison.comparison || []).map((c, i) => (
              <div key={c.platform}
                className={`comp-card ${i === 0 && c.complete_order ? 'comp-winner' : ''} ${!c.complete_order ? 'comp-incomplete' : ''}`}>
                <div className="comp-header">
                  <span className="comp-platform">{cap(c.platform)}</span>
                  <span className="comp-total">₹{c.grand_total || '—'}</span>
                </div>
                <div className="comp-items">
                  {(c.items_found || []).map((found, j) => (
                    <div className="comp-item-row" key={j}>
                      <span className="comp-item-query">{cap(found.query)}</span>
                      <span className="comp-item-product">{found.product}</span>
                      <span className="comp-item-price">
                        ₹{found.total_cost || found.price} 
                        {found.quantity > 1 && <span className="comp-math"> (₹{found.price}×{found.quantity})</span>}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Fee breakdown — show FREE badge when waived */}
                {(c.delivery_fee > 0 || c.handling_fee > 0 || c.platform_fee > 0 || c.gst_fee > 0
                  || c.fees_waived?.delivery || c.fees_waived?.platform) && (
                  <div className="comp-fees">
                    {(c.delivery_fee > 0 || c.fees_waived?.delivery) && (
                      <span>
                        Delivery:{' '}
                        {c.fees_waived?.delivery
                          ? <span className="fee-free">FREE</span>
                          : `₹${c.delivery_fee}`}
                      </span>
                    )}
                    {c.handling_fee > 0 && <span>Handling: ₹{c.handling_fee}</span>}
                    {(c.platform_fee > 0 || c.fees_waived?.platform) && (
                      <span>
                        Platform:{' '}
                        {c.fees_waived?.platform
                          ? <span className="fee-free">FREE</span>
                          : `₹${c.platform_fee}`}
                      </span>
                    )}
                    {c.gst_fee > 0 && <span>GST: ₹{c.gst_fee}</span>}
                  </div>
                )}

                {c.items_missing?.length > 0 && (
                  <p className="comp-missing">⚠ Not found: {c.items_missing.map(cap).join(', ')}</p>
                )}
              </div>
            ))}
            {comparison.fee_note && (
              <p className="comp-fee-note">ℹ {comparison.fee_note}</p>
            )}
          </div>
        )}

      </div>

      <div className="cart-footer">
        <button className="btn btn-compare"
          onClick={handleCompare}
          disabled={cart.length === 0 || comparing}>
          {comparing ? 'Comparing…' : '⚡ Compare Cart Totals'}
        </button>
      </div>
    </aside>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const auth  = useAuth();
  const token = auth.user?.access_token;

  const [query,       setQuery]       = useState('');
  const [pincode,     setPincode]     = useState('560095');
  const [results,     setResults]     = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);
  
  // Hoist cart state here
  const [cart, setCart] = useState([]);
  
  const loadCart = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getCart(token);
      setCart(data.cart || []);
    } catch (e) { console.error(e); }
  }, [token]);

  useEffect(() => { loadCart(); }, [loadCart]);

  useEffect(() => {
    if (token) syncMe(token).catch(console.error);
  }, [token]);

  if (auth.isLoading) {
    return (
      <div className="app auth-layout">
        <div className="auth-card">
          <div className="spinner" style={{ width: '64px', height: '64px', borderWidth: '5px' }} />
          <p style={{ color: 'var(--text-main)', fontSize: '1.2rem', marginTop: '1rem' }}>Connecting to Keycloak…</p>
        </div>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="app auth-layout">
        <div className="auth-card">
          <h1>
            <span className="auth-cart-icon">🛒</span>
            <span className="text-gradient">Bot<span>-Mart</span></span>
          </h1>
          <p>Compare prices across Blinkit, Zepto &amp; Instamart.<br />Log in to get started.</p>
          
          <div className="auth-platforms">
            <img src="/blinkit.png" alt="Blinkit" className="store-logo" title="Blinkit" />
            <img src="/zepto.png" alt="Zepto" className="store-logo" title="Zepto" />
            <img src="/instamart.png" alt="Instamart" className="store-logo" title="Instamart" />
          </div>

          <button className="btn-login" onClick={() => auth.signinRedirect()}>
            Log in with Keycloak
          </button>
        </div>
      </div>
    );
  }

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setResults(null);
    setError(null);
    try {
      const data = await comparePrices(query, pincode, token);
      setResults(data);
    } catch (err) {
      setError(err.message || 'Something went wrong. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  // AI-verified cheapest by TOTAL (item + fees)
  const cheapestTotalStore = results?.cheapest_total?.store;

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="logo">🛒 <span className="text-gradient">Bot<span>-Mart</span></span></div>
        <div className="header-right">
          <span className="username">👤 {auth.user?.profile?.preferred_username}</span>
          <button className="btn btn-logout" onClick={() => auth.signoutRedirect()}>Log Out</button>
        </div>
      </header>

      <div className="main">
        {/* LEFT: SEARCH + RESULTS */}
        <div className="search-panel">
          <h2>Compare prices in real-time</h2>

          <form className="search-form" onSubmit={handleSearch}>
            <input
              type="text"
              placeholder="Product name (e.g. Maggi, Milk)"
              value={query}
              onChange={e => setQuery(e.target.value)}
              required
            />
            <input
              type="text"
              placeholder="Pincode"
              value={pincode}
              onChange={e => setPincode(e.target.value)}
              style={{ flex: '0 0 140px' }}
              pattern="[0-9]{6}"
              required
            />
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? '🔍 Searching…' : '🔍 Compare'}
            </button>
          </form>

          {error && <div className="error-msg">{error}</div>}

          {loading && (
            <div className="loading-wrap">
              <div className="spinner" />
              <p>Scraping Blinkit, Zepto &amp; Instamart in parallel…</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.25rem' }}>
                AI will verify products match across platforms ✨
              </p>
            </div>
          )}

          {results && (
            <>
              {/* ── AI Note banner (shown when comparison isn't apples-to-apples) ── */}
              {results.ai_note && !results.comparison_valid && (
                <div className="ai-note-banner">
                  <span className="ai-icon">🤖</span>
                  <div>
                    <strong>AI Notice</strong>
                    <p>{results.ai_note}</p>
                  </div>
                </div>
              )}

              {/* ── Winner banner — cheapest by total price (AI-verified) ── */}
              {results.cheapest_total?.store && (
                <div className="winner-banner">
                  <span className="trophy">🏆</span>
                  <div>
                    <h3>Best Deal Including All Fees</h3>
                    <p className="winner-store">{results.cheapest_total.store}</p>
                    {results.canonical_name && (
                      <p className="winner-product">{results.canonical_name}</p>
                    )}
                    {results.ai_note && results.comparison_valid && (
                      <p className="winner-ai-note">🤖 {results.ai_note}</p>
                    )}
                  </div>
                  <div className="winner-price">
                    <sup>₹</sup>{results.cheapest_total.total_price}
                    <div className="winner-price-label">total</div>
                  </div>
                </div>
              )}

              {/* ── All result cards ── */}
              <div className="results-section">
                <div className="results-header">
                  <h2>
                    {results.canonical_name
                      ? `"${results.canonical_name}"`
                      : cap(results.query)}
                  </h2>
                  {!results.comparison_valid && (
                    <span className="comparison-invalid-badge">⚠ Mixed variants</span>
                  )}
                </div>

                <div className="results-grid">
                  {(results.all_results || []).map((item, i) => (
                    <ResultCard
                      key={i}
                      item={item}
                      isCheapestTotal={item.store === cheapestTotalStore && item.status === 'success'}
                      token={token}
                      searchQuery={query}
                      cart={cart}
                      refreshCart={loadCart}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* RIGHT: CART */}
        <CartPanel token={token} cart={cart} refreshCart={loadCart} pincode={pincode} />
      </div>
    </div>
  );
}