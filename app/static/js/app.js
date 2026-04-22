(function () {
    const navbar = document.getElementById('appNavbar');
    const reveals = document.querySelectorAll('.reveal-on-scroll');

    function updateNavbarState() {
        if (!navbar) return;
        if (window.scrollY > 8) {
            navbar.classList.add('is-scrolled');
        } else {
            navbar.classList.remove('is-scrolled');
        }
    }

    if (navbar) {
        updateNavbarState();
        window.addEventListener('scroll', updateNavbarState, { passive: true });
    }

    if (!reveals.length || !('IntersectionObserver' in window)) {
        reveals.forEach((el) => el.classList.add('is-visible'));
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                const delay = Number(entry.target.dataset.delay || 0) * 60;
                setTimeout(() => {
                    entry.target.classList.add('is-visible');
                }, delay);
                observer.unobserve(entry.target);
            });
        },
        { threshold: 0.12 }
    );

    reveals.forEach((el) => observer.observe(el));
})();
