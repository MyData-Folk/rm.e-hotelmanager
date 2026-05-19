import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getSavedApiKey() {
  return localStorage.getItem('admin_api_key') || '';
}

async function apiRequest(path, options = {}) {
  const apiKey = getSavedApiKey();

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      'X-Admin-Api-Key': apiKey,
    },
  });

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = typeof payload === 'object' ? payload.detail : payload;
    throw new Error(message || `Erreur API ${response.status}`);
  }

  return payload;
}

function StatCard({ label, value, hint }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  );
}

function ApiKeyPanel({ apiKey, setApiKey, onCheck, health, error }) {
  return (
    <section className="panel">
      <div>
        <p className="eyebrow">Connexion</p>
        <h2>Clé Admin</h2>
        <p className="muted">
          La première version protège les routes Admin avec le header X-Admin-Api-Key.
        </p>
      </div>

      <label>
        ADMIN_API_KEY
        <input
          type="password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          placeholder="dev-admin-key"
        />
      </label>

      <button onClick={onCheck}>Tester API Admin</button>

      {error && <p className="error">{error}</p>}
      {health && <pre>{JSON.stringify(health, null, 2)}</pre>}
    </section>
  );
}

function HotelCreatePanel({ onCreated }) {
  const [hotelId, setHotelId] = useState('folkestone');
  const [name, setName] = useState('Folkestone Opera');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function createHotel(event) {
    event.preventDefault();
    setMessage('');
    setError('');

    try {
      const hotel = await apiRequest('/admin/hotels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hotel_id: hotelId, name }),
      });

      setMessage(`Hôtel créé : ${hotel.name}`);
      onCreated?.(hotel.hotel_id);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="panel">
      <div>
        <p className="eyebrow">Hôtels</p>
        <h2>Créer un hôtel</h2>
        <p className="muted">
          La création ajoute aussi les réglages tarifaires par défaut : OTA-RO-FLEX, Double Classique, mode hybrid.
        </p>
      </div>

      <form className="grid-form" onSubmit={createHotel}>
        <label>
          Hotel ID
          <input value={hotelId} onChange={(event) => setHotelId(event.target.value)} />
        </label>

        <label>
          Nom
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>

        <button type="submit">Créer l’hôtel</button>
      </form>

      {message && <p className="success">{message}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function JsonUploadPanel({ selectedHotelId, onImported }) {
  const [hotelId, setHotelId] = useState(selectedHotelId || 'folkestone');
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (selectedHotelId) setHotelId(selectedHotelId);
  }, [selectedHotelId]);

  const stats = useMemo(() => {
    const source = importResult || analysis;
    if (!source) return null;

    return [
      ['Partenaires', source.partners_count ?? '-'],
      ['Plans détectés', source.plans_detected ?? '-'],
      ['Nouveaux plans', source.new_plans?.length ?? source.pending_configuration ?? 0],
      ['Suggestions référence', source.reference_suggestions?.length ?? 0],
    ];
  }, [analysis, importResult]);

  async function sendFile(path) {
    if (!file) {
      throw new Error('Sélectionne un fichier JSON.');
    }

    const formData = new FormData();
    formData.append('hotel_id', hotelId);
    formData.append('file', file);

    return apiRequest(path, {
      method: 'POST',
      body: formData,
    });
  }

  async function analyzeFile() {
    setError('');
    setAnalysis(null);
    setImportResult(null);

    try {
      const result = await sendFile('/admin/config/analyze');
      setAnalysis(result);
    } catch (err) {
      setError(err.message);
    }
  }

  async function uploadFile() {
    setError('');
    setImportResult(null);

    try {
      const result = await sendFile('/admin/upload/config');
      setImportResult(result);
      onImported?.(hotelId);
    } catch (err) {
      setError(err.message);
    }
  }

  const source = importResult || analysis;

  return (
    <section className="panel">
      <div>
        <p className="eyebrow">Configuration partenaires</p>
        <h2>Upload JSON OTA</h2>
        <p className="muted">
          Le JSON alimente les partenaires, commissions, remises et plans associés. Les plans inconnus passent en pending_configuration.
        </p>
      </div>

      <div className="grid-form">
        <label>
          Hotel ID
          <input value={hotelId} onChange={(event) => setHotelId(event.target.value)} />
        </label>

        <label>
          Fichier JSON
          <input
            type="file"
            accept=".json,application/json"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
      </div>

      <div className="actions">
        <button onClick={analyzeFile}>Analyser sans sauvegarder</button>
        <button className="primary" onClick={uploadFile}>Uploader et indexer</button>
      </div>

      {error && <p className="error">{error}</p>}

      {stats && (
        <div className="stats-grid">
          {stats.map(([label, value]) => (
            <StatCard key={label} label={label} value={value} />
          ))}
        </div>
      )}

      {source?.reference_suggestions?.length > 0 && (
        <div className="soft-box">
          <strong>Suggestions de plan de référence</strong>
          <div className="chips">
            {source.reference_suggestions.map((item) => (
              <span className="chip" key={item}>{item}</span>
            ))}
          </div>
        </div>
      )}

      {source?.new_plans?.length > 0 && (
        <div className="soft-box">
          <strong>Nouveaux plans détectés</strong>
          <div className="chips">
            {source.new_plans.slice(0, 40).map((item) => (
              <span className="chip warning" key={item}>{item}</span>
            ))}
          </div>
          {source.new_plans.length > 40 && (
            <p className="muted">+ {source.new_plans.length - 40} autres plans</p>
          )}
        </div>
      )}

      {importResult && (
        <p className="success">
          JSON importé. Action suivante : {importResult.next_action}
        </p>
      )}
    </section>
  );
}

function CatalogPanel({ selectedHotelId, refreshToken }) {
  const [hotelId, setHotelId] = useState(selectedHotelId || 'folkestone');
  const [catalog, setCatalog] = useState([]);
  const [pending, setPending] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (selectedHotelId) setHotelId(selectedHotelId);
  }, [selectedHotelId]);

  async function loadCatalog() {
    setError('');

    try {
      const [catalogResult, pendingResult] = await Promise.all([
        apiRequest(`/admin/rate-plans/catalog?hotel_id=${encodeURIComponent(hotelId)}`),
        apiRequest(`/admin/rate-plans/pending?hotel_id=${encodeURIComponent(hotelId)}`),
      ]);

      setCatalog(catalogResult);
      setPending(pendingResult);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadCatalog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  const activeCount = catalog.filter((item) => item.status === 'active').length;
  const pendingCount = catalog.filter((item) => item.status === 'pending_configuration').length;
  const ignoredCount = catalog.filter((item) => item.status === 'ignored').length;

  return (
    <section className="panel wide">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Catalogue</p>
          <h2>Plans tarifaires indexés</h2>
          <p className="muted">
            Liste des plans détectés dans le JSON partenaires et leur état de configuration.
          </p>
        </div>

        <div className="inline-controls">
          <input value={hotelId} onChange={(event) => setHotelId(event.target.value)} />
          <button onClick={loadCatalog}>Rafraîchir</button>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard label="Total plans" value={catalog.length} />
        <StatCard label="À configurer" value={pendingCount} />
        <StatCard label="Actifs" value={activeCount} />
        <StatCard label="Ignorés" value={ignoredCount} />
      </div>

      {error && <p className="error">{error}</p>}

      {pending.length > 0 && (
        <div className="soft-box">
          <strong>Plans en attente de configuration</strong>
          <div className="chips">
            {pending.slice(0, 60).map((item) => (
              <span className="chip warning" key={item.id}>{item.plan_code}</span>
            ))}
          </div>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Plan</th>
              <th>Statut</th>
              <th>Référence</th>
              <th>Règle active</th>
              <th>Partenaires</th>
            </tr>
          </thead>
          <tbody>
            {catalog.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.plan_code}</strong>
                  <small>{item.display_name}</small>
                </td>
                <td><span className={`status ${item.status}`}>{item.status}</span></td>
                <td>{item.is_reference ? item.reference_role || 'référence' : '-'}</td>
                <td>{item.has_active_rule ? 'Oui' : 'Non'}</td>
                <td>{item.partners?.slice(0, 3).join(', ') || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function App() {
  const [apiKey, setApiKey] = useState(getSavedApiKey());
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');
  const [selectedHotelId, setSelectedHotelId] = useState('folkestone');
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    if (apiKey) localStorage.setItem('admin_api_key', apiKey);
  }, [apiKey]);

  async function checkAdminHealth() {
    setError('');
    setHealth(null);

    try {
      const data = await apiRequest('/admin/health');
      setHealth(data);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="admin-layout">
      <aside className="sidebar">
        <p className="eyebrow">RM e-HotelManager</p>
        <h1>Admin</h1>
        <nav>
          <a href="#connexion">Connexion</a>
          <a href="#hotels">Hôtels</a>
          <a href="#json">JSON partenaires</a>
          <a href="#catalogue">Catalogue plans</a>
        </nav>
      </aside>

      <section className="content">
        <header className="hero">
          <div>
            <p className="eyebrow">Revenue Management Hôtelier</p>
            <h1>Configuration Admin</h1>
            <p>
              Gestion des hôtels, import JSON partenaires, indexation des plans tarifaires et détection des plans à configurer.
            </p>
          </div>
          <div className="hero-badge">
            Mode source par défaut
            <strong>hybrid</strong>
          </div>
        </header>

        <div id="connexion">
          <ApiKeyPanel
            apiKey={apiKey}
            setApiKey={setApiKey}
            onCheck={checkAdminHealth}
            health={health}
            error={error}
          />
        </div>

        <div id="hotels">
          <HotelCreatePanel onCreated={setSelectedHotelId} />
        </div>

        <div id="json">
          <JsonUploadPanel
            selectedHotelId={selectedHotelId}
            onImported={(hotelId) => {
              setSelectedHotelId(hotelId);
              setRefreshToken((value) => value + 1);
            }}
          />
        </div>

        <div id="catalogue">
          <CatalogPanel selectedHotelId={selectedHotelId} refreshToken={refreshToken} />
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
