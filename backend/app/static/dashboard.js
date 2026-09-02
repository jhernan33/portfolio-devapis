/**
 * Panel de analytics.
 *
 * Todo el contenido dinámico se inserta con createElement/textContent:
 * cualquier valor procedente de una petición se trata como texto, nunca como
 * marcado. Esto cerró un XSS almacenado vía cabecera HTTP.
 */
(function () {
    'use strict';

    function renderTable(tableId, headers, rows) {
        const table = document.getElementById(tableId);
        table.replaceChildren();

        const headRow = document.createElement('tr');
        for (const label of headers) {
            const th = document.createElement('th');
            th.textContent = label;
            headRow.appendChild(th);
        }
        table.appendChild(headRow);

        for (const cells of rows) {
            const tr = document.createElement('tr');
            for (const value of cells) {
                const td = document.createElement('td');
                td.textContent = value === null || value === undefined ? '—' : String(value);
                tr.appendChild(td);
            }
            table.appendChild(tr);
        }
    }

    function renderStats(summary) {
        const grid = document.getElementById('stats-grid');
        grid.replaceChildren();

        const cards = [
            [summary.total_visits, 'Visitas Totales'],
            [summary.unique_visitors, 'Visitantes Únicos'],
            [summary.recent_visits_7d, 'Últimos 7 Días'],
            [summary.today_visits, 'Hoy']
        ];

        for (const [value, label] of cards) {
            const card = document.createElement('div');
            card.className = 'stat-card';

            const valueEl = document.createElement('div');
            valueEl.className = 'stat-value';
            valueEl.textContent = value;

            const labelEl = document.createElement('div');
            labelEl.className = 'stat-label';
            labelEl.textContent = label;

            card.append(valueEl, labelEl);
            grid.appendChild(card);
        }
    }

    function formatDate(value) {
        if (!value) return '—';
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('es');
    }

    async function loadData() {
        try {
            const [analytics, recent] = await Promise.all([
                fetch('/api/analytics', { credentials: 'same-origin' }).then(r => r.json()),
                fetch('/api/analytics/recent?limit=10', { credentials: 'same-origin' }).then(r => r.json())
            ]);

            renderStats(analytics.summary);

            renderTable('browsers-table', ['Navegador', 'Visitas'],
                analytics.top_browsers.map(b => [b.browser, b.count]));

            renderTable('networks-table', ['Red (truncada)', 'Visitas', 'Última Visita'],
                analytics.top_networks.map(n => [n.ip_prefix, n.visits, formatDate(n.last_visit)]));

            renderTable('devices-table', ['Dispositivo', 'Visitas'],
                analytics.device_stats.map(d => [d.device_type, d.count]));

            // Las visitas recientes SÍ incluyen el tráfico interno, marcado
            // en su propia columna. Las estadísticas de arriba no lo cuentan.
            // Sin esta tabla no habría forma de distinguir "no llega nada"
            // de "llega y se está descartando".
            renderTable('recent-table', ['Red', 'Navegador', 'OS', 'Dispositivo', 'Origen', 'Fecha'],
                recent.visits.map(v => [
                    v.ip_prefix, v.browser, v.os, v.device_type,
                    v.is_internal ? 'interna' : 'externa',
                    formatDate(v.visited_at)
                ]));
        } catch (error) {
            console.error('Error loading data:', error);
        }
    }

    document.getElementById('refresh').addEventListener('click', loadData);
    loadData();
    setInterval(loadData, 30000);
})();
