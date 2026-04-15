(function () {
    const chartRoot = document.getElementById('nutrition-analytics-charts');
    if (!chartRoot) {
        return;
    }

    const endpoint = chartRoot.dataset.endpoint;

    function setMessage(id, message) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = message;
        }
    }

    function renderBarChart(items) {
        const canvas = document.getElementById('caloriesBarChart');
        if (!canvas) return;

        if (!items.length) {
            setMessage('barChartEmptyMessage', 'No calorie data available yet. Analyze a few meals first.');
            return;
        }

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: items.map((item) => item.label),
                datasets: [{
                    label: 'Calories',
                    data: items.map((item) => item.value),
                    backgroundColor: 'rgba(209, 139, 47, 0.65)',
                    borderColor: 'rgba(209, 139, 47, 1)',
                    borderWidth: 1,
                    borderRadius: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#3f5163',
                            maxRotation: 45,
                            minRotation: 25,
                        },
                        grid: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#3f5163' },
                        grid: { color: 'rgba(80, 101, 124, 0.15)' },
                    },
                },
            },
        });
    }

    function renderPieChart(macros) {
        const canvas = document.getElementById('macroPieChart');
        if (!canvas) return;

        const values = [macros.protein || 0, macros.carbohydrates || 0, macros.fats || 0];
        const total = values.reduce((sum, value) => sum + value, 0);

        if (!total) {
            setMessage('pieChartEmptyMessage', 'No macro data available yet.');
            return;
        }

        new Chart(canvas, {
            type: 'pie',
            data: {
                labels: ['Protein', 'Carbohydrates', 'Fats'],
                datasets: [{
                    data: values,
                    backgroundColor: [
                        'rgba(15, 140, 104, 0.8)',
                        'rgba(95, 120, 146, 0.78)',
                        'rgba(185, 59, 53, 0.78)',
                    ],
                    borderColor: '#ffffff',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#34495c',
                            padding: 14,
                        },
                    },
                },
            },
        });
    }

    function renderLineChart(timeline) {
        const canvas = document.getElementById('timelineLineChart');
        if (!canvas) return;

        if (!timeline.length) {
            setMessage('lineChartEmptyMessage', 'No timeline data available yet.');
            return;
        }

        new Chart(canvas, {
            type: 'line',
            data: {
                labels: timeline.map((point) => point.date),
                datasets: [{
                    label: 'Calories',
                    data: timeline.map((point) => point.calories),
                    borderColor: 'rgba(46, 63, 82, 1)',
                    backgroundColor: 'rgba(46, 63, 82, 0.15)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 4,
                    pointBackgroundColor: 'rgba(26, 36, 48, 0.95)',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { color: '#3f5163' },
                        grid: { color: 'rgba(80, 101, 124, 0.12)' },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#3f5163' },
                        grid: { color: 'rgba(80, 101, 124, 0.15)' },
                    },
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#34495c',
                        },
                    },
                },
            },
        });
    }

    fetch(endpoint, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch nutrition analytics data');
            }
            return response.json();
        })
        .then((payload) => {
            renderBarChart(payload.calories_by_meal || []);
            renderPieChart(payload.macros_distribution || {});
            renderLineChart(payload.timeline_data || []);
        })
        .catch(() => {
            setMessage('barChartEmptyMessage', 'Could not load chart data.');
            setMessage('pieChartEmptyMessage', 'Could not load chart data.');
            setMessage('lineChartEmptyMessage', 'Could not load chart data.');
        });
})();
