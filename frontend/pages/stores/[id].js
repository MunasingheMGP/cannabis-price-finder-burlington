import Link from 'next/link';
import Navbar from '../../components/Navbar';

const API = process.env.API_BASE || 'http://localhost:8000';

export async function getServerSideProps({ params }) {
  try {
    const res = await fetch(`${API}/api/stores/${params.id}`);
    if (!res.ok) return { notFound: true };
    const store = await res.json();
    return { props: { store } };
  } catch {
    return { notFound: true };
  }
}

export default function StoreDetail({ store }) {
  const deals = (store.products || []).filter((p) => p.sale_price);

  return (
    <>
      <Navbar />
      <div className="page-header">
        <div className="breadcrumb">
          <Link href="/">Home</Link>
          <span className="breadcrumb-sep">/</span>
          <Link href="/stores">Stores</Link>
          <span className="breadcrumb-sep">/</span>
          <span>{store.store_name}</span>
        </div>
        <h1 className="page-title">{store.store_name}</h1>
        <p className="page-subtitle">{store.address}, {store.city}, ON {store.postal_code}</p>
      </div>

      <div className="detail-grid">
        {/* PRODUCTS */}
        <div>
          <div className="info-panel">
            <div className="info-panel-title">
              Products in Stock
              <span className="badge badge-green" style={{ marginLeft: 12 }}>{store.products?.length || 0} items</span>
              {deals.length > 0 && (
                <span className="badge badge-sale" style={{ marginLeft: 8 }}>{deals.length} on sale</span>
              )}
            </div>
            {store.products?.length === 0 ? (
              <p style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>No product data available for this store.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Brand</th>
                    <th>Size</th>
                    <th>Regular</th>
                    <th>Sale</th>
                  </tr>
                </thead>
                <tbody>
                  {store.products?.map((p, i) => {
                    const id = p.product_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
                    return (
                      <tr key={i}>
                        <td><Link href={`/products/${id}`}>{p.product_name}</Link></td>
                        <td style={{ color: 'var(--lime)', fontSize: '0.82rem' }}>{p.brand || '—'}</td>
                        <td style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>{p.size_format || '—'}</td>
                        <td>{p.regular_price || '—'}</td>
                        <td>{p.sale_price ? <span style={{ color: 'var(--amber)' }}>{p.sale_price}</span> : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* SIDEBAR */}
        <div className="detail-sidebar">
          <div className="info-panel">
            <div className="info-panel-title">Store Details</div>
            <div className="info-row">
              <span className="info-key">Address</span>
              <span className="info-val">{store.address}</span>
            </div>
            <div className="info-row">
              <span className="info-key">City</span>
              <span className="info-val">{store.city}, ON</span>
            </div>
            <div className="info-row">
              <span className="info-key">Postal Code</span>
              <span className="info-val">{store.postal_code}</span>
            </div>
            <div className="info-row">
              <span className="info-key">Phone</span>
              <span className="info-val">{store.phone_number !== 'Not listed' ? store.phone_number : '—'}</span>
            </div>
            <div className="info-row">
              <span className="info-key">Distance</span>
              <span className="info-val">{store.distance_km} km from Burlington</span>
            </div>
            {store.owner_details && store.owner_details !== 'Not publicly disclosed' && (
              <div className="info-row">
                <span className="info-key">Owner</span>
                <span className="info-val">{store.owner_details}</span>
              </div>
            )}
            {/* {store.website && (
              <div className="info-row">
                <span className="info-key">Website</span>
                <span className="info-val">
                  <a href={store.website} target="_blank" rel="noreferrer"
                    style={{ color: 'var(--lime)', fontSize: '0.82rem' }}>
                    Visit site ↗
                  </a>
                </span>
              </div>
            )} */}
          </div>

          {store.hours_of_operation && store.hours_of_operation !== 'Not listed' && store.hours_of_operation !== 'Pending' && (
            <div className="info-panel">
              <div className="info-panel-title">Hours of Operation</div>
              <p style={{ fontSize: '0.82rem', color: 'var(--muted)', lineHeight: 1.8 }}>
                {store.hours_of_operation}
              </p>
            </div>
          )}

          <Link href="/stores" className="btn btn-outline" style={{ width: '100%', justifyContent: 'center' }}>
            ← Back to Stores
          </Link>
        </div>
      </div>

      <footer>
        <p>GreenLeaf · <Link href="/">Home</Link></p>
      </footer>
    </>
  );
}
