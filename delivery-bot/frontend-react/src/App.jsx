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

// Capitalize each word of a search query for display: "semi skimmed milk" → "Semi Skimmed Milk"
const cap = (str) => str ? str.replace(/\b\w/g, c => c.toUpperCase()) : str;

// ── Store badge helper ──────────────────────────────────────────────────────
function StoreBadge({ store, cheapest }) {
  const cls = `store-badge badge-${(store || 'unknown').toLowerCase()}`;
  return (
    <>
      <span className={cls}>{store || 'Unknown'}</span>
      {cheapest && <span className="store-badge badge-cheapest">Cheapest</span>}
    </>
  );
}

// Single result card
function ResultCard({ item, isCheapest, token, searchQuery, onAddedToCart }) {
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  const handleAdd = async () => {
    setAdding(true);
    try {
      // KEY FIX: pass searchQuery (e.g. 'milk'), not item.name ('Amul Taaza Toned Milk')
      // This way all three platforms can be matched for the same item in cart compare
      await addToCart(searchQuery, 1, token);
      setAdded(true);
      onAddedToCart();
      setTimeout(() => setAdded(false), 2000);
    } catch (e) {
      console.error(e);
    } finally {
      setAdding(false);
    }
  };

  if (item.status !== 'success') {
    return (
      <div className="result-card failed">
        <StoreBadge store={item.store} />
        <p className="card-error">{item.error || 'Scrape failed'}</p>
      </div>
    );
  }

  return (
    <div className={`result-card ${isCheapest ? 'cheapest' : ''}`}>
      <div>
        <StoreBadge store={item.store} cheapest={isCheapest} />
      </div>
      <p className="card-name">{item.name}</p>
      <div className="card-footer">
        <div className="card-price"><sup>₹</sup>{item.price}</div>
        <button
          className="btn btn-cart"
          onClick={handleAdd}
          disabled={adding}
        >
          {added ? '✓ Added' : adding ? 'Adding...' : '+ Cart'}
        </button>
      </div>
    </div>
  );
}

// ── Cart Panel ──────────────────────────────────────────────────────────────
function CartPanel({ token, refreshTrigger, pincode }) {
  const [cart, setCart] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [clearing, setClearing] = useState(false);

  const loadCart = useCallback(async () => {
    try {
      const data = await getCart(token);
      setCart(data.cart || []);
    } catch (e) {
      console.error(e);
    }
  }, [token]);

  useEffect(() => { loadCart(); }, [loadCart, refreshTrigger]);

  const handleRemove = async (id) => {
    try {
      await removeFromCart(id, token);
      setCart(prev => prev.filter(i => i.id !== id));
      setComparison(null);
    } catch (e) { console.error(e); }
  };

  const handleClear = async () => {
    setClearing(true);
    try {
      await clearCart(token);
      setCart([]);
      setComparison(null);
    } catch (e) { console.error(e); } finally { setClearing(false); }
  };

  const handleCompare = async () => {
    setComparing(true);
    setComparison(null);
    try {
      const data = await compareCartTotals(pincode || '560095', token);
      setComparison(data);
    } catch (e) {
      console.error(e);
    } finally { setComparing(false); }
  };

  return (
    <aside className="cart-panel">
      <div className="cart-header">
        <h3>🛒 My Cart <span className="cart-count">{cart.length}</span></h3>
        {cart.length > 0 && (
          <button className="btn btn-secondary" style={{fontSize:'0.75rem', padding:'0.3rem 0.7rem'}} onClick={handleClear} disabled={clearing}>
            {clearing ? '...' : 'Clear'}
          </button>
        )}
      </div>

      <div className="cart-body">
        {cart.length === 0 && (
          <p className="cart-empty">Your cart is empty.<br/>Search for a product and add items.</p>
        )}
        {cart.map(item => (
          <div className="cart-item" key={item.id}>
            <span className="cart-item-name">{cap(item.search_query)}</span>
            <span className="cart-item-qty">×{item.quantity}</span>
            <button className="btn-remove" onClick={() => handleRemove(item.id)}>✕</button>
          </div>
        ))}

        {/* Cart Comparison Results */}
        {comparison && (
          <div className="comparison">
            <h4 style={{fontSize:'0.85rem', color:'var(--muted)', marginBottom:'0.5rem'}}>
              {comparison.cheapest_platform
                ? `🏆 Best: ${comparison.cheapest_platform}${comparison.you_save ? ` — Save ₹${comparison.you_save}` : ''}`
                : 'No complete results'}
            </h4>
            {(comparison.comparison || []).map((c, i) => (
              <div key={c.platform} className={`comp-card ${i === 0 && c.complete_order ? 'comp-winner' : ''} ${!c.complete_order ? 'comp-incomplete' : ''}`}>
                <div className="comp-header">
                  <span className="comp-platform">{cap(c.platform)}</span>
                  <span className="comp-total">₹{c.grand_total || '—'}</span>
                </div>

                {/* Per-item breakdown */}
                <div className="comp-items">
                  {(c.items_found || []).map((found, j) => (
                    <div className="comp-item-row" key={j}>
                      <span className="comp-item-query">{cap(found.query)}</span>
                      <span className="comp-item-product">{found.product}</span>
                      <span className="comp-item-price">₹{found.price}</span>
                    </div>
                  ))}
                </div>

                {/* Extra fees (when scrapers capture them) */}
                {(c.delivery_fee > 0 || c.handling_fee > 0 || c.platform_fee > 0 || c.gst_fee > 0) && (
                  <div className="comp-fees">
                    {c.delivery_fee > 0 && <span>Delivery: ₹{c.delivery_fee}</span>}
                    {c.handling_fee > 0 && <span>Handling: ₹{c.handling_fee}</span>}
                    {c.platform_fee > 0 && <span>Platform: ₹{c.platform_fee}</span>}
                    {c.gst_fee > 0 && <span>GST: ₹{c.gst_fee}</span>}
                  </div>
                )}

                {c.items_missing?.length > 0 && (
                  <p className="comp-missing">⚠ Not found: {c.items_missing.map(cap).join(', ')}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="cart-footer">
        <button
          className="btn btn-compare"
          onClick={handleCompare}
          disabled={cart.length === 0 || comparing}
        >
          {comparing ? 'Comparing...' : '⚡ Compare Cart Totals'}
        </button>
      </div>
    </aside>
  );
}

// ── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const auth = useAuth();
  const token = auth.user?.access_token;

  const [query, setQuery] = useState('');
  const [pincode, setPincode] = useState('560095');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [cartTrigger, setCartTrigger] = useState(0);

  // Sync this user to our DB on first login
  useEffect(() => {
    if (token) syncMe(token).catch(console.error);
  }, [token]);

  // ── Loading state ──
  if (auth.isLoading) {
    return (
      <div className="auth-screen">
        <div className="spinner" />
        <p style={{color:'var(--muted)'}}>Connecting to Keycloak...</p>
      </div>
    );
  }

  // ── Not logged in ──
  if (!auth.isAuthenticated) {
    return (
      <div className="auth-screen">
        <h1>🛒 Bot<span>-Mart</span></h1>
        <p>Compare prices across Blinkit, Zepto & Instamart. Log in to get started.</p>
        <button className="btn-login" onClick={() => auth.signinRedirect()}>
          Log in with Keycloak
        </button>
      </div>
    );
  }

  // ── Search handler ──
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

  const cheapestStore = results?.cheapest_option?.store;

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="logo">🛒 Bot<span>-Mart</span></div>
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
              {loading ? 'Searching...' : '🔍 Compare'}
            </button>
          </form>

          {error && <div className="error-msg">{error}</div>}

          {loading && (
            <div className="loading-wrap">
              <div className="spinner" />
              <p>Orchestrating scrapers across Blinkit, Zepto & Instamart...</p>
            </div>
          )}

          {results && (
            <>
              {/* Winner banner */}
              {results.cheapest_option && (
                <div className="winner-banner">
                  <span className="trophy">🏆</span>
                  <div>
                    <h3>Best Price Found</h3>
                    <p>{results.cheapest_option.store} — {results.cheapest_option.name}</p>
                  </div>
                  <div className="winner-price"><sup>₹</sup>{results.cheapest_option.price}</div>
                </div>
              )}

              {/* All result cards */}
              <div className="results-section">
                <h2>All Results</h2>
                <div className="results-grid">
                  {(results.all_results || []).map((item, i) => (
                    <ResultCard
                      key={i}
                      item={item}
                      isCheapest={item.store === cheapestStore && item.status === 'success'}
                      token={token}
                      searchQuery={query}  // Pass the original search query
                      onAddedToCart={() => setCartTrigger(t => t + 1)}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* RIGHT: CART */}
        <CartPanel
          token={token}
          refreshTrigger={cartTrigger}
          pincode={pincode}
        />
      </div>
    </div>
  );
}