import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('admin_api_key') || '');
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');

  async function checkAdminHealth() {
    setError('');
    setHealth(null);

    try {
      const response = await fetch(`${API_URL}/admin/health`, {
        headers: { 'X-Admin-Api-Key': apiKey },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Erreur API Admin');
      }

      setHealth(data);
    } catch (err) {
      setError(err.message || 'Impossible de joindre l’API Admin');
    }
  }

  useEffect(() => {
    if (apiKey) localStorage.setItem('admin_api_key', apiKey);
  }, [apiKey]);

  return (
    <main className="shell">
      <section className="card">
        <p className="eyebrow">RM e-HotelManager</p>
        <h1>Admin Revenue Management</h1>
        <p className="muted">
          Configuration hôtels, imports Excel/JSON, règles tarifaires et pilotage OTA-RO-FLEX.
        </p>

        <label>
          ADMIN_API_KEY
          <input
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="Saisir la clé admin"
          />
        </label>

        <button onClick={checkAdminHealth}>Tester API Admin</button>

        {error && <p className="error">{error}</p>}
        {health && <pre>{JSON.stringify(health, null, 2)}</pre>}
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
