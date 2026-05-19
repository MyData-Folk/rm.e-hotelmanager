import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  BarChart3,
  CalendarDays,
  Download,
  Hotel,
  Play,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import './style.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEFAULT_FILTERS = {
  hotelId: 'folkestone',
  start: '2026-05-13',
  end: '2026-05-14',
  roomName: 'Double Classique',
  planCode: 'OTA-RO-NANR',
  partnerName: 'Booking.com (6562)',
  sourceMode: 'hybrid',
  promoDiscount: 0,
};

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Erreur API ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Keep the generic message.
    }
    throw new Error(message);
  }

  return response.json();
}

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-';
  }
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone || ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusPill({ status }) {
  const label = {
    available: 'Disponible',
    sold_out: 'Complet',
    not_available_for_sale: 'Fermé',
    unknown: 'Inconnu',
    out_of_range: 'Hors plage',
  }[status] || status || 'Inconnu';

  return <span className={`pill ${status || 'unknown'}`}>{label}</span>;
}

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [health, setHealth] = useState(null);
  const [hotels, setHotels] = useState([]);
  const [partners, setPartners] = useState([]);
  const [availability, setAvailability] = useState([]);
  const [rates, setRates] = useState([]);
  const [grid, setGrid] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const partner = useMemo(
    () => partners.find((item) => item.name === filters.partnerName),
    [partners, filters.partnerName],
  );

  const availableRooms = useMemo(
    () => unique([
      ...availability.map((item) => item.room_name),
      ...rates.map((item) => item.room_name),
      filters.roomName,
    ]),
    [availability, rates, filters.roomName],
  );

  const availablePlans = useMemo(
    () => unique([
      ...(partner?.plan_codes || []),
      ...rates.map((item) => item.plan_code),
      filters.planCode,
    ]),
    [partner, rates, filters.planCode],
  );

  const dashboardSummary = useMemo(() => {
    const availableCells = availability.filter((item) => item.status === 'available');
    const totalStock = availableCells.reduce(
      (sum, item) => sum + (item.available_quantity || 0),
      0,
    );
    const prices = rates.map((item) => item.price).filter((value) => value !== null);
    const averageRate = prices.length
      ? prices.reduce((sum, value) => sum + value, 0) / prices.length
      : null;

    return {
      rooms: unique(availability.map((item) => item.room_name)).length,
      availableCells: availableCells.length,
      totalStock,
      averageRate,
    };
  }, [availability, rates]);

  function updateFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
  }

  async function refreshData(nextFilters = filters) {
    setLoading(true);
    setMessage('');
    try {
      const query = new URLSearchParams({
        hotel_id: nextFilters.hotelId,
        start: nextFilters.start,
        end: nextFilters.end,
      });
      const gridQuery = new URLSearchParams({
        hotel_id: nextFilters.hotelId,
        start: nextFilters.start,
        end: nextFilters.end,
        rooms: nextFilters.roomName,
        plans: nextFilters.planCode,
        source_mode: nextFilters.sourceMode,
      });

      const [healthPayload, hotelsPayload, partnersPayload, availabilityPayload, ratesPayload, gridPayload] = await Promise.all([
        apiRequest('/health'),
        apiRequest('/hotels'),
        apiRequest(`/partners?hotel_id=${encodeURIComponent(nextFilters.hotelId)}`),
        apiRequest(`/availability?${query.toString()}`),
        apiRequest(`/imported-rates?${query.toString()}`),
        apiRequest(`/rates/grid?${gridQuery.toString()}`),
      ]);

      setHealth(healthPayload);
      setHotels(hotelsPayload);
      setPartners(partnersPayload);
      setAvailability(availabilityPayload);
      setRates(ratesPayload);
      setGrid(gridPayload);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function runSimulation() {
    setLoading(true);
    setMessage('');
    try {
      const payload = await apiRequest('/simulate', {
        method: 'POST',
        body: JSON.stringify({
          hotel_id: filters.hotelId,
          room_name: filters.roomName,
          plan_code: filters.planCode,
          partner_name: filters.partnerName,
          source_mode: filters.sourceMode,
          start: filters.start,
          end: filters.end,
          promo_discount: Number(filters.promoDiscount || 0),
        }),
      });
      setSimulation(payload);
      setActiveTab('simulation');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshData(DEFAULT_FILTERS);
  }, []);

  const tabs = [
    ['dashboard', Activity, 'Dashboard'],
    ['simulation', SlidersHorizontal, 'Simulation'],
    ['availability', CalendarDays, 'Disponibilités'],
    ['rates', BarChart3, 'Grille tarifaire'],
    ['exports', Download, 'Exports'],
  ];

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Hotel size={22} /></div>
          <div>
            <strong>RM e-HotelManager</strong>
            <span>Interface utilisateur</span>
          </div>
        </div>

        <nav className="nav-tabs">
          {tabs.map(([id, Icon, label]) => (
            <button
              key={id}
              className={activeTab === id ? 'active' : ''}
              onClick={() => setActiveTab(id)}
              title={label}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="api-status">
          <span className={health?.status === 'ok' ? 'dot ok' : 'dot'} />
          <span>{health?.status === 'ok' ? 'API connectée' : 'API en attente'}</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Consultation revenue</h1>
            <p>Données publiques, simulation OTA et lecture hybride calculée/Excel.</p>
          </div>
          <button className="icon-button" onClick={() => refreshData()} disabled={loading} title="Rafraîchir">
            <RefreshCw size={18} />
          </button>
        </header>

        <section className="filters-band">
          <label>
            Hôtel
            <input
              value={filters.hotelId}
              list="hotels"
              onChange={(event) => updateFilter('hotelId', event.target.value)}
            />
          </label>
          <datalist id="hotels">
            {hotels.map((hotel) => (
              <option key={hotel.hotel_id} value={hotel.hotel_id}>{hotel.name}</option>
            ))}
          </datalist>

          <label>
            Début
            <input type="date" value={filters.start} onChange={(event) => updateFilter('start', event.target.value)} />
          </label>
          <label>
            Fin
            <input type="date" value={filters.end} onChange={(event) => updateFilter('end', event.target.value)} />
          </label>
          <label>
            Chambre
            <input
              value={filters.roomName}
              list="rooms"
              onChange={(event) => updateFilter('roomName', event.target.value)}
            />
          </label>
          <datalist id="rooms">
            {availableRooms.map((room) => <option key={room} value={room} />)}
          </datalist>
          <label>
            Plan
            <input
              value={filters.planCode}
              list="plans"
              onChange={(event) => updateFilter('planCode', event.target.value)}
            />
          </label>
          <datalist id="plans">
            {availablePlans.map((plan) => <option key={plan} value={plan} />)}
          </datalist>
          <label>
            Source
            <select value={filters.sourceMode} onChange={(event) => updateFilter('sourceMode', event.target.value)}>
              <option value="hybrid">Hybrid</option>
              <option value="calculated">Calculated</option>
              <option value="excel">Excel</option>
            </select>
          </label>
          <button className="primary-action" onClick={() => refreshData()} disabled={loading}>
            <Search size={17} />
            Charger
          </button>
        </section>

        {message && <div className="notice">{message}</div>}

        {activeTab === 'dashboard' && (
          <section className="view">
            <div className="stat-grid">
              <Stat label="Chambres suivies" value={dashboardSummary.rooms} />
              <Stat label="Cellules disponibles" value={dashboardSummary.availableCells} tone="green" />
              <Stat label="Stock total" value={dashboardSummary.totalStock} />
              <Stat label="Prix moyen importé" value={formatMoney(dashboardSummary.averageRate)} />
            </div>

            <div className="split-layout">
              <section className="panel">
                <h2>Partenaires OTA</h2>
                <div className="partner-list">
                  {partners.slice(0, 10).map((item) => (
                    <button
                      key={item.id}
                      className={item.name === filters.partnerName ? 'partner-row selected' : 'partner-row'}
                      onClick={() => {
                        updateFilter('partnerName', item.name);
                        if (item.plan_codes[0]) updateFilter('planCode', item.plan_codes[0]);
                      }}
                    >
                      <span>{item.name}</span>
                      <small>{item.commission}% commission · {item.plan_codes.length} plans</small>
                    </button>
                  ))}
                </div>
              </section>

              <section className="panel">
                <h2>État période</h2>
                <div className="compact-table">
                  {availability.slice(0, 8).map((item) => (
                    <div className="table-row" key={`${item.room_name}-${item.date}`}>
                      <span>{item.date}</span>
                      <span>{item.room_name}</span>
                      <StatusPill status={item.status} />
                      <strong>{item.available_quantity ?? '-'}</strong>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </section>
        )}

        {activeTab === 'simulation' && (
          <section className="view">
            <section className="simulation-bar">
              <label>
                Partenaire
                <input
                  value={filters.partnerName}
                  list="partners"
                  onChange={(event) => updateFilter('partnerName', event.target.value)}
                />
              </label>
              <datalist id="partners">
                {partners.map((item) => <option key={item.id} value={item.name} />)}
              </datalist>
              <label>
                Promo %
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={filters.promoDiscount}
                  onChange={(event) => updateFilter('promoDiscount', event.target.value)}
                />
              </label>
              <button className="primary-action" onClick={runSimulation} disabled={loading}>
                <Play size={17} />
                Simuler
              </button>
            </section>

            {simulation ? (
              <>
                <div className="stat-grid">
                  <Stat label="Brut" value={formatMoney(simulation.summary.subtotal_brut)} />
                  <Stat label="Remises" value={formatMoney(simulation.summary.total_discount || (simulation.summary.total_partner_discount + simulation.summary.total_promo_discount))} />
                  <Stat label="Commission" value={formatMoney(simulation.summary.total_commission)} />
                  <Stat label="Net" value={formatMoney(simulation.summary.total_net)} tone="green" />
                </div>
                <section className="panel">
                  <h2>Résultats par nuit</h2>
                  <div className="data-grid rates-grid">
                    <span>Date</span>
                    <span>Plan</span>
                    <span>Stock</span>
                    <span>Prix brut</span>
                    <span>Net</span>
                    {simulation.results.map((item) => (
                      <React.Fragment key={`${item.date}-${item.plan_code}`}>
                        <strong>{item.date_display}</strong>
                        <span>{item.plan_code}</span>
                        <span>{item.stock ?? '-'}</span>
                        <span>{formatMoney(item.gross_price)}</span>
                        <strong>{formatMoney(item.net_price)}</strong>
                      </React.Fragment>
                    ))}
                  </div>
                </section>
              </>
            ) : (
              <section className="empty-state">Lance une simulation pour afficher les montants nets par nuit.</section>
            )}
          </section>
        )}

        {activeTab === 'availability' && (
          <section className="view panel">
            <h2>Disponibilités</h2>
            <div className="data-grid availability-grid">
              <span>Date</span>
              <span>Chambre</span>
              <span>Statut</span>
              <span>Stock</span>
              {availability.map((item) => (
                <React.Fragment key={`${item.date}-${item.room_name}`}>
                  <strong>{item.date}</strong>
                  <span>{item.room_name}</span>
                  <StatusPill status={item.status} />
                  <strong>{item.available_quantity ?? '-'}</strong>
                </React.Fragment>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'rates' && (
          <section className="view panel">
            <h2>Grille tarifaire</h2>
            <div className="data-grid rates-grid">
              <span>Date</span>
              <span>Chambre</span>
              <span>Plan</span>
              <span>Source</span>
              <span>Prix</span>
              {(grid?.items || []).map((item) => (
                <React.Fragment key={`${item.date}-${item.room_name}-${item.plan_code}`}>
                  <strong>{item.date}</strong>
                  <span>{item.room_name}</span>
                  <span>{item.plan_code}</span>
                  <span>{item.source_used || '-'}</span>
                  <strong>{formatMoney(item.price)}</strong>
                </React.Fragment>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'exports' && (
          <section className="view">
            <div className="export-actions">
              <button onClick={() => downloadJson(`availability-${filters.hotelId}.json`, availability)}>
                <Download size={18} />
                Disponibilités JSON
              </button>
              <button onClick={() => downloadJson(`rates-${filters.hotelId}.json`, grid || {})}>
                <Download size={18} />
                Grille JSON
              </button>
              <button onClick={() => downloadJson(`simulation-${filters.hotelId}.json`, simulation || {})}>
                <Download size={18} />
                Simulation JSON
              </button>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
