import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => response.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'error' }));
  }, []);

  return (
    <main className="shell">
      <section className="card">
        <p className="eyebrow">RM e-HotelManager</p>
        <h1>Interface utilisateur</h1>
        <p className="muted">
          Consultation, simulations, disponibilités et résultats Revenue Management.
        </p>
        <pre>{JSON.stringify(health, null, 2)}</pre>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
