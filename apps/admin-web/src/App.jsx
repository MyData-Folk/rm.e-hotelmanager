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
          Les routes Admin sont protégées par le header X-Admin-Api-Key.
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

      setMessage(`Hôtel prêt : ${hotel.name}`);
      onCreated?.(hotel.hotel_id);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="panel">
      <div>
        <p className="eyebrow">Hôtels</p>
        <h2>Créer ou initialiser un hôtel</h2>
        <p className="muted">
          La création ajoute les réglages tarifaires par défaut : OTA-RO-FLEX, Double Classique, mode hybrid.
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

  const source = importResult || analysis;

  const stats = useMemo(() => {
    if (!source) return null;
    return [
      ['Partenaires', source.partners_count ?? '-'],
      ['Plans détectés', source.plans_detected ?? '-'],
      ['Plans connus', source.known_plans?.length ?? 0],
      ['Nouveaux plans', source.new_plans?.length ?? source.pending_configuration ?? 0],
    ];
  }, [source]);

  async function sendFile(path) {
    if (!file) throw new Error('Sélectionne un fichier JSON.');

    const formData = new FormData();
    formData.append('hotel_id', hotelId);
    formData.append('file', file);

    return apiRequest(path, { method: 'POST', body: formData });
  }

  async function analyzeFile() {
    setError('');
    setAnalysis(null);
    setImportResult(null);

    try {
      setAnalysis(await sendFile('/admin/config/analyze'));
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
            {source.new_plans.slice(0, 60).map((item) => (
              <span className="chip warning" key={item}>{item}</span>
            ))}
          </div>
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

function RulesPanel({ selectedHotelId, onRulesImported }) {
  const [hotelId, setHotelId] = useState(selectedHotelId || 'folkestone');
  const [file, setFile] = useState(null);
  const [rules, setRules] = useState([]);
  const [selectedPlanCode, setSelectedPlanCode] = useState('');
  const [basePrice, setBasePrice] = useState(200);
  const [roundingMode, setRoundingMode] = useState('');
  const [roundingIncrement, setRoundingIncrement] = useState('');
  const [importResult, setImportResult] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (selectedHotelId) setHotelId(selectedHotelId);
  }, [selectedHotelId]);

  async function loadRules() {
    setError('');

    try {
      const result = await apiRequest(`/admin/rules/rate-plans?hotel_id=${encodeURIComponent(hotelId)}`);
      setRules(result);

      if (!selectedPlanCode && result.length > 0) {
        setSelectedPlanCode(result[0].plan_code);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function importCsv() {
    setError('');
    setImportResult(null);

    if (!file) {
      setError('Sélectionne un fichier CSV.');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('hotel_id', hotelId);
      formData.append('default_rounding_mode', 'two_decimals');
      formData.append('file', file);

      const result = await apiRequest('/admin/rules/rate-plans/import-csv', {
        method: 'POST',
        body: formData,
      });

      setImportResult(result);
      await loadRules();
      onRulesImported?.();
    } catch (err) {
      setError(err.message);
    }
  }

  async function testRule() {
    setError('');
    setTestResult(null);

    if (!selectedPlanCode) {
      setError('Sélectionne un plan tarifaire.');
      return;
    }

    const payload = {
      hotel_id: hotelId,
      plan_code: selectedPlanCode,
      base_price: Number(basePrice),
    };

    if (roundingMode) payload.rounding_mode = roundingMode;
    if (roundingIncrement !== '') payload.rounding_increment = Number(roundingIncrement);

    try {
      const result = await apiRequest('/admin/rules/rate-plans/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      setTestResult(result);
    } catch (err) {
      setError(err.message);
    }
  }

  const enabledRules = rules.filter((rule) => rule.enabled).length;
  const totalSteps = rules.reduce((sum, rule) => sum + (rule.steps?.length || 0), 0);

  return (
    <section className="panel wide">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Règles tarifaires</p>
          <h2>Moteur de calcul des plans</h2>
          <p className="muted">
            Importe le CSV de logique tarifaire, visualise les étapes et teste le calcul avec trace.
          </p>
        </div>

        <div className="inline-controls">
          <input value={hotelId} onChange={(event) => setHotelId(event.target.value)} />
          <button onClick={loadRules}>Charger</button>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard label="Règles" value={rules.length} />
        <StatCard label="Actives" value={enabledRules} />
        <StatCard label="Étapes" value={totalSteps} />
        <StatCard label="Arrondi défaut" value="2 déc." />
      </div>

      <div className="soft-box">
        <strong>Importer un CSV de règles</strong>
        <div className="grid-form">
          <label>
            Fichier CSV
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
          </label>

          <button className="primary" onClick={importCsv}>Importer les règles</button>
        </div>
      </div>

      {importResult && (
        <div className="soft-box">
          <strong>Import terminé</strong>
          <div className="stats-grid">
            <StatCard label="Règles importées" value={importResult.rules_imported} />
            <StatCard label="Étapes importées" value={importResult.steps_imported} />
            <StatCard label="Erreurs" value={importResult.errors?.length || 0} />
            <StatCard label="Délimiteur" value={importResult.delimiter || '-'} />
          </div>

          {importResult.errors?.length > 0 && (
            <pre>{JSON.stringify(importResult.errors.slice(0, 20), null, 2)}</pre>
          )}
        </div>
      )}

      <div className="soft-box">
        <strong>Tester une règle</strong>

        <div className="grid-form four">
          <label>
            Plan
            <select value={selectedPlanCode} onChange={(event) => setSelectedPlanCode(event.target.value)}>
              <option value="">Sélectionner</option>
              {rules.map((rule) => (
                <option key={rule.id} value={rule.plan_code}>
                  {rule.plan_code}
                </option>
              ))}
            </select>
          </label>

          <label>
            Prix de base
            <input
              type="number"
              value={basePrice}
              onChange={(event) => setBasePrice(event.target.value)}
            />
          </label>

          <label>
            Arrondi test
            <select value={roundingMode} onChange={(event) => setRoundingMode(event.target.value)}>
              <option value="">Règle par défaut</option>
              <option value="none">none</option>
              <option value="two_decimals">two_decimals</option>
              <option value="nearest_euro">nearest_euro</option>
              <option value="ceil_euro">ceil_euro</option>
              <option value="floor_euro">floor_euro</option>
              <option value="nearest_increment">nearest_increment</option>
              <option value="ceil_increment">ceil_increment</option>
              <option value="floor_increment">floor_increment</option>
            </select>
          </label>

          <label>
            Incrément
            <input
              type="number"
              step="0.01"
              value={roundingIncrement}
              onChange={(event) => setRoundingIncrement(event.target.value)}
              placeholder="0.50 / 1 / 5"
            />
          </label>
        </div>

        <button onClick={testRule}>Tester la règle</button>

        {testResult && (
          <div className="result-grid">
            <StatCard label="Raw result" value={testResult.raw_result} />
            <StatCard label="Rounded" value={testResult.rounded_result} />
            <StatCard label="Base source" value={testResult.base_source} />
            <StatCard label="Arrondi" value={testResult.rounding_mode} />
          </div>
        )}

        {testResult?.trace?.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Étape</th>
                  <th>Opération</th>
                  <th>Valeur</th>
                  <th>Avant</th>
                  <th>Après</th>
                </tr>
              </thead>

              <tbody>
                {testResult.trace.map((step) => (
                  <tr key={step.step_order}>
                    <td>{step.step_order}</td>
                    <td>{step.operation}</td>
                    <td>{step.value}</td>
                    <td>{step.before}</td>
                    <td><strong>{step.after}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Plan</th>
              <th>Source</th>
              <th>Arrondi</th>
              <th>Actif</th>
              <th>Étapes</th>
            </tr>
          </thead>

          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td><strong>{rule.plan_code}</strong></td>
                <td>{rule.base_source}</td>
                <td>{rule.rounding_mode}</td>
                <td>{rule.enabled ? 'Oui' : 'Non'}</td>
                <td>
                  <div className="steps-line">
                    {rule.steps?.length ? (
                      rule.steps.map((step) => (
                        <span className="chip" key={step.id}>
                          {step.step_order}. {step.operation} {step.value}
                        </span>
                      ))
                    ) : (
                      <span className="muted">Aucune étape</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const DEFAULT_ROOMS = [
  'Double Classique',
  'Double Single Use Classique',
  'Twin Classique',
  'Double Classique Terrasse',
  'Double Deluxe',
  'Twin Deluxe',
  'Double Deluxe Terrasse',
  'Deux Chambres Adjacentes 4 personnes',
];

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function addDays(isoDate, days) {
  const date = new Date(`${isoDate}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function dateRange(start, end) {
  const output = [];
  const current = new Date(`${start}T00:00:00`);
  const limit = new Date(`${end}T00:00:00`);

  if (Number.isNaN(current.getTime()) || Number.isNaN(limit.getTime()) || current > limit) {
    return output;
  }

  while (current <= limit) {
    output.push(current.toISOString().slice(0, 10));
    current.setDate(current.getDate() + 1);
  }

  return output;
}

function splitLines(value) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function RatePilotagePanel({ selectedHotelId }) {
  const today = isoToday();
  const [hotelId, setHotelId] = useState(selectedHotelId || 'folkestone');
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(addDays(today, 6));
  const [roomsText, setRoomsText] = useState(DEFAULT_ROOMS.join('\n'));
  const [plansText, setPlansText] = useState('OTA-RO-FLEX\nCWT-BB-FLEX');
  const [sourceMode, setSourceMode] = useState('hybrid');
  const [baseRates, setBaseRates] = useState({});
  const [bulkPrice, setBulkPrice] = useState('');
  const [preview, setPreview] = useState(null);
  const [saveResult, setSaveResult] = useState(null);
  const [recalculateResult, setRecalculateResult] = useState(null);
  const [grid, setGrid] = useState(null);
  const [conflicts, setConflicts] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (selectedHotelId) setHotelId(selectedHotelId);
  }, [selectedHotelId]);

  const dates = useMemo(() => dateRange(start, end), [start, end]);
  const rooms = useMemo(() => splitLines(roomsText), [roomsText]);
  const plans = useMemo(() => splitLines(plansText), [plansText]);
  const referencePlan = plans[0] || 'OTA-RO-FLEX';

  function updateBaseRate(day, value) {
    setBaseRates((current) => ({
      ...current,
      [day]: value,
    }));
  }

  function applyBulkPrice() {
    if (bulkPrice === '') return;

    setBaseRates((current) => {
      const next = { ...current };
      dates.forEach((day) => {
        next[day] = bulkPrice;
      });
      return next;
    });
  }

  async function previewFirstRate() {
    setError('');
    setPreview(null);

    const day = dates.find((item) => baseRates[item] !== '' && baseRates[item] !== undefined);
    if (!day) {
      setError('Renseigne au moins un tarif de référence.');
      return;
    }

    try {
      const result = await apiRequest('/admin/rates/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hotel_id: hotelId,
          date: day,
          base_price: Number(baseRates[day]),
          rooms,
          plans,
        }),
      });

      setPreview(result);
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveBaseRates() {
    setError('');
    setSaveResult(null);

    const rates = dates
      .filter((day) => baseRates[day] !== '' && baseRates[day] !== undefined)
      .map((day) => ({
        date: day,
        base_price: Number(baseRates[day]),
      }));

    if (!rates.length) {
      setError('Aucun tarif à sauvegarder.');
      return;
    }

    try {
      const result = await apiRequest('/admin/rates/base/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hotel_id: hotelId,
          rates,
          rooms,
          plans,
        }),
      });

      setSaveResult(result);
      await loadGrid();
    } catch (err) {
      setError(err.message);
    }
  }

  async function recalculateRates() {
    setError('');
    setRecalculateResult(null);

    try {
      const result = await apiRequest('/admin/rates/recalculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hotel_id: hotelId,
          start,
          end,
          rooms,
          plans,
        }),
      });

      setRecalculateResult(result);
      await loadGrid();
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadGrid() {
    setError('');
    setGrid(null);

    try {
      const query = new URLSearchParams({
        hotel_id: hotelId,
        start,
        end,
        rooms: rooms.join(','),
        plans: plans.join(','),
        source_mode: sourceMode,
      });

      setGrid(await apiRequest(`/admin/rates/grid?${query.toString()}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadConflicts() {
    setError('');
    setConflicts(null);

    try {
      const query = new URLSearchParams({
        hotel_id: hotelId,
        start,
        end,
        rooms: rooms.join(','),
        plans: plans.join(','),
      });

      setConflicts(await apiRequest(`/admin/rates/conflicts?${query.toString()}`));
    } catch (err) {
      setError(err.message);
    }
  }

  const gridRows = useMemo(() => {
    if (!grid?.items?.length) return [];

    return grid.items.reduce((rows, item) => {
      const key = `${item.date}|${item.room_name}`;
      if (!rows[key]) {
        rows[key] = {
          date: item.date,
          room_name: item.room_name,
          plans: {},
        };
      }
      rows[key].plans[item.plan_code] = item;
      return rows;
    }, {});
  }, [grid]);

  return (
    <section className="panel wide">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Pilotage tarifs</p>
          <h2>Tarif de référence et recalcul</h2>
          <p className="muted">
            Saisie OTA-RO-FLEX, preview des règles, sauvegarde BaseRate et recalcul DerivedRate.
          </p>
        </div>

        <div className="inline-controls">
          <input value={hotelId} onChange={(event) => setHotelId(event.target.value)} />
          <select value={sourceMode} onChange={(event) => setSourceMode(event.target.value)}>
            <option value="hybrid">hybrid</option>
            <option value="calculated">calculated</option>
            <option value="excel">excel</option>
          </select>
        </div>
      </div>

      <div className="rate-layout">
        <div className="soft-box">
          <strong>Période</strong>
          <div className="grid-form">
            <label>
              Début
              <input type="date" value={start} onChange={(event) => setStart(event.target.value)} />
            </label>
            <label>
              Fin
              <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
            </label>
          </div>

          <label>
            Chambres
            <textarea value={roomsText} onChange={(event) => setRoomsText(event.target.value)} rows={8} />
          </label>

          <label>
            Plans
            <textarea value={plansText} onChange={(event) => setPlansText(event.target.value)} rows={4} />
          </label>
        </div>

        <div className="soft-box">
          <strong>Saisie {referencePlan}</strong>
          <div className="bulk-bar">
            <input
              type="number"
              min="0"
              step="0.01"
              value={bulkPrice}
              onChange={(event) => setBulkPrice(event.target.value)}
              placeholder="Prix à appliquer"
            />
            <button onClick={applyBulkPrice}>Appliquer</button>
          </div>

          <div className="rate-date-grid">
            {dates.map((day) => (
              <label className="rate-day" key={day}>
                <span>{day}</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={baseRates[day] || ''}
                  onChange={(event) => updateBaseRate(day, event.target.value)}
                  placeholder="OTA"
                />
              </label>
            ))}
          </div>

          <div className="actions">
            <button onClick={previewFirstRate}>Preview</button>
            <button className="primary" onClick={saveBaseRates}>Sauvegarder</button>
            <button onClick={recalculateRates}>Recalculer</button>
          </div>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {(saveResult || recalculateResult || grid) && (
        <div className="stats-grid">
          <StatCard label="BaseRate" value={saveResult?.base_rates_saved ?? '-'} />
          <StatCard label="DerivedRate" value={saveResult?.derived_rates_saved ?? recalculateResult?.derived_rates_saved ?? '-'} />
          <StatCard label="Dates recalculées" value={recalculateResult?.recalculated_dates?.length ?? '-'} />
          <StatCard label="Manquants grille" value={grid?.summary?.missing_count ?? '-'} />
        </div>
      )}

      {preview && (
        <div className="soft-box">
          <strong>Preview {preview.date}</strong>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Chambre</th>
                  <th>Plan</th>
                  <th>Prix</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {preview.calculations.slice(0, 80).map((item) => (
                  <tr key={`${item.room_name}-${item.plan_code}`}>
                    <td>{item.room_name}</td>
                    <td><strong>{item.plan_code}</strong></td>
                    <td>{item.price}</td>
                    <td>{item.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="actions">
        <button onClick={loadGrid}>Charger la grille</button>
        <button onClick={loadConflicts}>Voir les conflits</button>
      </div>

      {grid && (
        <div className="soft-box">
          <strong>Grille tarifaire</strong>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Chambre</th>
                  {plans.map((plan) => (
                    <th key={plan}>{plan}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.values(gridRows).slice(0, 120).map((row) => (
                  <tr key={`${row.date}-${row.room_name}`}>
                    <td>{row.date}</td>
                    <td>{row.room_name}</td>
                    {plans.map((plan) => {
                      const item = row.plans[plan];
                      return (
                        <td key={plan}>
                          {item?.missing ? (
                            <span className="status inactive">missing</span>
                          ) : (
                            <>
                              <strong>{item?.price}</strong>
                              <small>{item?.source_used}</small>
                            </>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {conflicts && (
        <div className="soft-box">
          <strong>Conflits calculated vs Excel</strong>
          <div className="stats-grid">
            <StatCard label="Conflits" value={conflicts.summary?.conflicts_count ?? 0} />
            <StatCard label="Écarts" value={conflicts.summary?.mismatch_count ?? 0} />
            <StatCard label="Calculated manquant" value={conflicts.summary?.missing_calculated_count ?? 0} />
            <StatCard label="Excel manquant" value={conflicts.summary?.missing_excel_count ?? 0} />
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Chambre</th>
                  <th>Plan</th>
                  <th>Calculated</th>
                  <th>Excel</th>
                  <th>Écart</th>
                </tr>
              </thead>
              <tbody>
                {conflicts.conflicts?.slice(0, 120).map((item) => (
                  <tr key={`${item.date}-${item.room_name}-${item.plan_code}`}>
                    <td>{item.date}</td>
                    <td>{item.room_name}</td>
                    <td>{item.plan_code}</td>
                    <td>{item.calculated_price ?? '-'}</td>
                    <td>{item.excel_price ?? '-'}</td>
                    <td><strong>{item.difference ?? '-'}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
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
      setHealth(await apiRequest('/admin/health'));
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
          <a href="#rules">Règles tarifaires</a>
          <a href="#pilotage">Pilotage tarifs</a>
        </nav>
      </aside>

      <section className="content">
        <header className="hero">
          <div>
            <p className="eyebrow">Revenue Management Hôtelier</p>
            <h1>Configuration Admin</h1>
            <p>
              Gestion des hôtels, import JSON partenaires, indexation des plans et moteur de règles tarifaires.
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

        <div id="rules">
          <RulesPanel
            selectedHotelId={selectedHotelId}
            onRulesImported={() => setRefreshToken((value) => value + 1)}
          />
        </div>

        <div id="pilotage">
          <RatePilotagePanel selectedHotelId={selectedHotelId} />
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
