(function () {
    const items = document.querySelectorAll('.landing-reveal');
    if (!items.length) return;

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                const delay = Number(entry.target.dataset.delay || 0) * 55;
                setTimeout(() => entry.target.classList.add('is-visible'), delay);
                observer.unobserve(entry.target);
            });
        },
        { threshold: 0.15 }
    );

    items.forEach((item) => observer.observe(item));
})();
