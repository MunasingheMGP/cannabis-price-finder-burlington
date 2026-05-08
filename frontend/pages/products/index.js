import { useState } from 'react';
import Link from 'next/link';
import Navbar from '../../components/Navbar';

const API = process.env.API_BASE || 'http://localhost:8000';

// ── Category keyword map ───────────────────────────────────────────────────────
// Product names are matched (case-insensitive) against these keywords.
// First match wins; unmatched products fall into "Other".
const CATEGORY_RULES = [
  { label: 'Flower',      keywords: ['flower', 'bud', 'cannabis', 'indica', 'sativa', 'hybrid', 'dried'] },
  { label: 'Pre-Roll',    keywords: ['pre-roll', 'preroll', 'joint', 'blunt', 'cone'] },
  { label: 'Vape',        keywords: ['vape', 'vaporizer', 'cartridge', 'cart', 'pod', 'pen'] },
  { label: 'Edible',      keywords: ['edible', 'gummy', 'gummies', 'chocolate', 'cookie', 'brownie', 'candy', 'chew', 'mint', 'lozenge'] },
  { label: 'Beverage',    keywords: ['beverage', 'drink', 'shot', 'tea', 'coffee', 'sparkling', 'water', 'soda'] },
  { label: 'Concentrate', keywords: ['concentrate', 'shatter', 'wax', 'resin', 'rosin', 'hash', 'oil', 'distillate', 'extract', 'dab'] },
  { label: 'Tincture',    keywords: ['tincture', 'drops', 'spray', 'sublingual'] },
  { label: 'Topical',     keywords: ['topical', 'cream', 'balm', 'lotion', 'patch', 'gel', 'salve'] },
  { label: 'Capsule',     keywords: ['capsule', 'softgel', 'pill', 'tablet'] },
  { label: 'Accessory',   keywords: ['accessory', 'grinder', 'paper', 'filter', 'lighter', 'pipe', 'bong'] },
];

function detectCategory(productName = '', sizeFormat = '') {
  const haystack = (productName + ' ' + sizeFormat).toLowerCase();
  for (const rule of CATEGORY_RULES) {
    if (rule.keywords.some((kw) => haystack.includes(kw))) return rule.label;
  }
  return 'Other';
}

// ── Data fetching ──────────────────────────────────────────────────────────────
export async function getServerSideProps({ query }) {
  const params = new URLSearchParams();
  if (query.brand)     params.set('brand',     query.brand);
  if (query.city)      params.set('city',       query.city);
  if (query.min_price) params.set('min_price',  query.min_price);
  if (query.max_price) params.set('max_price',  query.max_price);
  params.set('limit', '500');

  try {
    const res      = await fetch(`${API}/api/products?${params}`);
    const data     = await res.json();
    const raw      = data.products || [];

    // Attach detected category to every product
    const products = raw.map((p) => ({
      ...p,
      category: detectCategory(p.product_name, p.size_format),
    }));

    // Derive unique filter options
    const brands     = [...new Set(products.map((p) => p.brand).filter(Boolean))].sort();
    const cities     = [...new Set(products.map((p) => p.store_city).filter(Boolean))].sort();
    const categories = [...new Set(products.map((p) => p.category))].sort();

    return { props: { products, brands, cities, categories, filters: query } };
  } catch {
    return { props: { products: [], brands: [], cities: [], categories: [], filters: {} } };
  }
}

// ── Page component ─────────────────────────────────────────────────────────────
export default function ProductsPage({ products, brands, cities, categories, filters }) {
  const [brand,    setBrand]    = useState(filters.brand     || '');
  const [city,     setCity]     = useState(filters.city      || '');
  const [category, setCategory] = useState(filters.category  || '');
  const [minPrice, setMinPrice] = useState(filters.min_price || '');
  const [maxPrice, setMaxPrice] = useState(filters.max_price || '');

  // ── Apply filters (server-side for brand / city / price, client-side for category)
  const applyFilters = () => {
    const p = new URLSearchParams();
    if (brand)    p.set('brand',     brand);
    if (city)     p.set('city',      city);
    if (minPrice) p.set('min_price', minPrice);
    if (maxPrice) p.set('max_price', maxPrice);
    // Category is resolved client-side so we pass it as a plain query param
    if (category) p.set('category', category);
    window.location.href = `/products?${p}`;
  };

  const clearFilters = () => { window.location.href = '/products'; };

  // ── Client-side category filter + deduplication ────────────────────────────
  const seen   = new Set();
  const unique = products
    .filter((p) => !category || p.category === category)
    .filter((p) => {
      if (seen.has(p.id)) return false;
      seen.add(p.id);
      return true;
    });

  // ── Category pill colours ──────────────────────────────────────────────────
  const CATEGORY_COLORS = {
    'Flower':      { bg: '#EAF3DE', color: '#3B6D11' },
    'Pre-Roll':    { bg: '#E1F5EE', color: '#0F6E56' },
    'Vape':        { bg: '#E6F1FB', color: '#185FA5' },
    'Edible':      { bg: '#FAEEDA', color: '#854F0B' },
    'Beverage':    { bg: '#E6F1FB', color: '#185FA5' },
    'Concentrate': { bg: '#FCEBEB', color: '#A32D2D' },
    'Tincture':    { bg: '#FBEAF0', color: '#993556' },
    'Topical':     { bg: '#EEEDFE', color: '#534AB7' },
    'Capsule':     { bg: '#F1EFE8', color: '#5F5E5A' },
    'Accessory':   { bg: '#F1EFE8', color: '#5F5E5A' },
    'Other':       { bg: '#F1EFE8', color: '#5F5E5A' },
  };

  const catStyle = (cat) => CATEGORY_COLORS[cat] || CATEGORY_COLORS['Other'];

  return (
    <>
      <Navbar />

      <div className="page-header">
        <h1 className="page-title">All Products</h1>
        <p className="page-subtitle">
          {unique.length} products
          {category ? ` in "${category}"` : ''}
          {' '}across {cities.length} cities
        </p>
      </div>

      <div className="container">

        {/* ── FILTER BAR ── */}
        <div className="filter-bar">

          {/* Category */}
          <div className="filter-group">
            <label className="filter-label">Category</label>
            <select
              className="filter-select"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Brand */}
          <div className="filter-group">
            <label className="filter-label">Brand</label>
            <select
              className="filter-select"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
            >
              <option value="">All brands</option>
              {brands.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>

          {/* City */}
          <div className="filter-group">
            <label className="filter-label">City</label>
            <select
              className="filter-select"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            >
              <option value="">All cities</option>
              {cities.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Min price */}
          <div className="filter-group">
            <label className="filter-label">Min Price ($)</label>
            <input
              className="filter-input"
              type="number"
              placeholder="0"
              value={minPrice}
              onChange={(e) => setMinPrice(e.target.value)}
              style={{ width: 100 }}
            />
          </div>

          {/* Max price */}
          <div className="filter-group">
            <label className="filter-label">Max Price ($)</label>
            <input
              className="filter-input"
              type="number"
              placeholder="999"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
              style={{ width: 100 }}
            />
          </div>

          {/* Buttons */}
          <div className="filter-group" style={{ justifyContent: 'flex-end', marginLeft: 'auto' }}>
            <label className="filter-label">&nbsp;</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={applyFilters}>Apply</button>
              <button className="btn btn-outline" onClick={clearFilters}>Clear</button>
            </div>
          </div>

        </div>

        {/* ── CATEGORY QUICK-FILTER PILLS ── */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
          <button
            onClick={() => setCategory('')}
            style={{
              padding: '4px 14px',
              borderRadius: 20,
              border: '1px solid var(--color-border-secondary)',
              background: category === '' ? 'var(--color-text-primary)' : 'transparent',
              color:      category === '' ? 'var(--color-background-primary)' : 'var(--color-text-secondary)',
              fontSize: '0.78rem',
              cursor: 'pointer',
            }}
          >
            All
          </button>
          {categories.map((cat) => {
            const active = category === cat;
            const s = catStyle(cat);
            return (
              <button
                key={cat}
                onClick={() => setCategory(active ? '' : cat)}
                style={{
                  padding: '4px 14px',
                  borderRadius: 20,
                  border: `1px solid ${s.color}40`,
                  background: active ? s.color : s.bg,
                  color: active ? '#fff' : s.color,
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  fontWeight: active ? 500 : 400,
                }}
              >
                {cat}
              </button>
            );
          })}
        </div>

        {/* ── PRODUCT GRID ── */}
        {unique.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🌿</div>
            <h3>No products found</h3>
            <p>Try adjusting your filters.</p>
          </div>
        ) : (
          <div className="card-grid" style={{ marginBottom: 60 }}>
            {unique.map((p, i) => {
              const s = catStyle(p.category);
              return (
                <Link href={`/products/${p.id}`} className="card" key={i}>
                  {/* Category pill */}
                  <span style={{
                    display: 'inline-block',
                    padding: '2px 10px',
                    borderRadius: 12,
                    fontSize: '0.7rem',
                    fontWeight: 500,
                    background: s.bg,
                    color: s.color,
                    marginBottom: 8,
                  }}>
                    {p.category}
                  </span>

                  <div className="product-brand">{p.brand || 'Unknown Brand'}</div>
                  <div className="product-name">{p.product_name}</div>
                  {p.size_format && <div className="product-size">{p.size_format}</div>}

                  <div className="price-row">
                    {p.sale_price ? (
                      <>
                        <span className="price-sale">{p.sale_price}</span>
                        <span className="price-was">{p.regular_price}</span>
                        <span className="badge badge-sale">SALE</span>
                      </>
                    ) : (
                      <span className="price-regular">{p.regular_price || '—'}</span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}

      </div>

      <footer>
        <p>GreenLeaf · <Link href="/">Home</Link></p>
      </footer>
    </>
  );
}