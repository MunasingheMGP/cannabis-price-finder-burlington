import { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Navbar from '../components/Navbar';

const API = process.env.API_BASE || 'http://localhost:8000';

// Cannabis product categories with keyword mappings
const CATEGORIES = [
  { label: 'Flower',       icon: '🌿', slug: 'flower'      },
  { label: 'Pre-Rolls',    icon: '🚬', slug: 'pre-roll'    },
  { label: 'Vapes',        icon: '💨', slug: 'vape'        },
  { label: 'Edibles',      icon: '🍬', slug: 'edible'      },
  { label: 'Concentrates', icon: '🔬', slug: 'concentrate' },
  { label: 'Tinctures',    icon: '💧', slug: 'tincture'    },
  { label: 'Topicals',     icon: '🧴', slug: 'topical'     },
  { label: 'Capsules',     icon: '💊', slug: 'capsule'     },
];

export async function getServerSideProps() {
  try {
    const [statsRes, dealsRes, storesRes] = await Promise.all([
      fetch(`${API}/api/stats`),
      fetch(`${API}/api/deals?limit=6`),
      fetch(`${API}/api/stores?limit=6`),
    ]);
    const stats  = await statsRes.json();
    const deals  = await dealsRes.json();
    const stores = await storesRes.json();
    return { props: { stats, deals: deals.deals || [], stores: stores.stores || [] } };
  } catch {
    return { props: { stats: {}, deals: [], stores: [] } };
  }
}

export default function Home({ stats, deals, stores }) {
  const router = useRouter();
  const [q, setQ] = useState('');

  const handleSearch = (e) => {
    e.preventDefault();
    if (q.trim().length > 1) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <>
      <Navbar />

      {/* HERO */}
      <section className="hero">
        <div className="hero-eyebrow">📍 Burlington, ON · 35 km radius</div>
        <h1>Find the best cannabis<br /><em>prices near you</em></h1>
        <p className="hero-sub">
          Compare prices across licensed retailers, discover local deals,
          and find stores stocking exactly what you need.
        </p>
        <form className="hero-search" onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="Search products, brands, stores…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">Search</button>
        </form>
      </section>

      {/* STATS */}
      <div className="stats-bar">
        {[
          { n: stats.stores,   label: 'Licensed Stores' },
          { n: stats.products, label: 'Products' },
          { n: stats.brands,   label: 'Brands' },
          { n: stats.deals,    label: 'Active Deals' },
          { n: stats.cities,   label: 'Cities' },
        ].map((s) => (
          <div className="stat-item" key={s.label}>
            <div className="stat-number">{s.n ?? '—'}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {/*  CATEGORY NAVIGATION  */}
      <div className="container" style={{ marginBottom: 56 }}>
        <div className="section-header">
          <h2 className="section-title">Shop by Category</h2>
          <Link href="/products" className="section-link">View all products →</Link>
        </div>
        <div className="category-grid">
          {CATEGORIES.map((cat) => (
            <Link
              key={cat.slug}
              href={`/products?category=${encodeURIComponent(cat.slug)}`}
              className="category-card"
            >
              <div className="category-icon">{cat.icon}</div>
              <div className="category-label">{cat.label}</div>
            </Link>
          ))}
        </div>
      </div>
      

      {/* FEATURED DEALS */}
      <div className="container" style={{ marginBottom: 56 }}>
        <div className="section-header">
          <h2 className="section-title">🔥 Hot Deals</h2>
          <Link href="/deals" className="section-link">View all deals →</Link>
        </div>
        <div className="card-grid-sm">
          {deals.map((d, i) => (
            <Link href={`/products/${d.id}`} className="card deal-card" key={i}>
              <div className="product-brand">{d.brand || 'Unknown Brand'}</div>
              <div className="product-name">{d.product_name}</div>
              <div className="product-size">{d.size_format}</div>
              <div className="price-row">
                <span className="price-sale">{d.sale_price}</span>
                <span className="price-was">{d.regular_price}</span>
                <span className="badge badge-sale">SALE</span>
              </div>
              {d.promotion_duration && d.promotion_duration !== 'Not listed' && (
                <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 8 }}>
                  Until {d.promotion_duration}
                </div>
              )}
            </Link>
          ))}
        </div>
        {deals.length === 0 && (
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>No deals available right now.</p>
        )}
      </div>

      {/* NEARBY STORES */}
      <div className="container" style={{ marginBottom: 60 }}>
        <div className="section-header">
          <h2 className="section-title">Nearby Stores</h2>
          <Link href="/stores" className="section-link">View all stores →</Link>
        </div>
        <div className="card-grid">
          {stores.map((s, i) => (
            <Link href={`/stores/${s.id}`} className="card" key={i}>
              <div className="store-card-name">{s.store_name}</div>
              <div className="store-meta">
                <span>📍 {s.city}</span>
                {s.phone_number && s.phone_number !== 'Not listed' && (
                  <span>📞 {s.phone_number}</span>
                )}
                <span style={{ marginTop: 4 }}>
                  <span className="badge badge-green">{s.distance_km} km away</span>
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      <footer>
        <p>GreenLeaf · Burlington, ON cannabis price comparison · Data from AGCO registry &amp; licensed retailers</p>
      </footer>
    </>
  );
}