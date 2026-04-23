(function () {
    const chartDataElement = document.getElementById('weeklyTrackingChartData');
    if (!chartDataElement || typeof Chart === 'undefined') {
        return;
    }

    let chartData;
    try {
        chartData = JSON.parse(chartDataElement.textContent || '{}');
    } catch (_error) {
        return;
    }

    const labels = chartData.labels || [];
    const caloriesByDay = chartData.calories_by_day || [];
    const mealsByDay = chartData.meals_by_day || [];
    const macros = chartData.macros_distribution || {};

    function setMessage(id, message) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = message;
        }
    }

    function toggleEmptyState(id, show) {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle('d-none', !show);
    }

    const caloriesCanvas = document.getElementById('weeklyCaloriesChart');
    if (caloriesCanvas) {
        const hasCalories = caloriesByDay.some((value) => Number(value) > 0);
        if (!hasCalories) {
            setMessage('weeklyCaloriesChartMessage', 'No calorie data in this week.');
            toggleEmptyState('weeklyCaloriesChartEmpty', true);
            caloriesCanvas.classList.add('d-none');
        } else {
            toggleEmptyState('weeklyCaloriesChartEmpty', false);
            caloriesCanvas.classList.remove('d-none');
            new Chart(caloriesCanvas, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Calories',
                            data: caloriesByDay,
                            backgroundColor: 'rgba(240, 138, 31, 0.65)',
                            borderColor: 'rgba(219, 119, 6, 1)',
                            borderWidth: 1,
                            borderRadius: 8,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        x: {
                            ticks: { color: '#3d546b' },
                            grid: { display: false },
                        },
                        y: {
                            beginAtZero: true,
                            ticks: { color: '#3d546b' },
                            grid: { color: 'rgba(87, 112, 137, 0.15)' },
                        },
                    },
                },
            });
        }
    }

    const macroCanvas = document.getElementById('weeklyMacroChart');
    if (macroCanvas) {
        const macroValues = [
            Number(macros.protein || 0),
            Number(macros.carbohydrates || 0),
            Number(macros.fats || 0),
        ];

        if (!macroValues.some((value) => value > 0)) {
            setMessage('weeklyMacroChartMessage', 'No macronutrient data in this week.');
            toggleEmptyState('weeklyMacroChartEmpty', true);
            macroCanvas.classList.add('d-none');
        } else {
            toggleEmptyState('weeklyMacroChartEmpty', false);
            macroCanvas.classList.remove('d-none');
            new Chart(macroCanvas, {
                type: 'doughnut',
                data: {
                    labels: ['Protein', 'Carbohydrates', 'Fats'],
                    datasets: [
                        {
                            data: macroValues,
                            backgroundColor: [
                                'rgba(16, 185, 129, 0.82)',
                                'rgba(59, 130, 246, 0.78)',
                                'rgba(124, 58, 237, 0.78)',
                            ],
                            borderColor: '#ffffff',
                            borderWidth: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '62%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#354b62',
                                padding: 14,
                            },
                        },
                    },
                },
            });
        }
    }

    const mealsCanvas = document.getElementById('weeklyMealsChart');
    if (mealsCanvas) {
        const hasMeals = mealsByDay.some((value) => Number(value) > 0);
        if (!hasMeals) {
            setMessage('weeklyMealsChartMessage', 'No meals logged in this week.');
            toggleEmptyState('weeklyMealsChartEmpty', true);
            mealsCanvas.classList.add('d-none');
        } else {
            toggleEmptyState('weeklyMealsChartEmpty', false);
            mealsCanvas.classList.remove('d-none');
            new Chart(mealsCanvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Meals Logged',
                            data: mealsByDay,
                            borderColor: 'rgba(30, 64, 175, 0.95)',
                            backgroundColor: 'rgba(30, 64, 175, 0.15)',
                            fill: true,
                            tension: 0.35,
                            pointRadius: 4,
                            pointBackgroundColor: 'rgba(30, 64, 175, 0.95)',
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#354b62',
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: { color: '#3d546b' },
                            grid: { color: 'rgba(87, 112, 137, 0.12)' },
                        },
                        y: {
                            beginAtZero: true,
                            ticks: {
                                color: '#3d546b',
                                precision: 0,
                            },
                            grid: { color: 'rgba(87, 112, 137, 0.15)' },
                        },
                    },
                },
            });
        }
    }
})();
