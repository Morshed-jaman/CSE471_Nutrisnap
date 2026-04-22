(function () {
    const metricValues = document.querySelectorAll('.home-metric h3');
    if (!metricValues.length) {
        return;
    }

    metricValues.forEach((el) => {
        const target = Number((el.textContent || '').replace(/[^0-9.]/g, ''));
        if (!Number.isFinite(target)) {
            return;
        }

        const duration = 700;
        const startTime = performance.now();

        function tick(now) {
            const progress = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const value = Math.round(target * eased);
            el.textContent = String(value);
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }

        requestAnimationFrame(tick);
    });
})();
