(function () {
    "use strict";

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const menuButton = document.querySelector(".premium-menu-toggle");
    const menu = document.querySelector(".premium-nav-links");

    if (menuButton && menu) {
        menuButton.addEventListener("click", () => {
            const isOpen = menu.classList.toggle("is-open");
            menuButton.setAttribute("aria-expanded", String(isOpen));
        });
        menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
            menu.classList.remove("is-open");
            menuButton.setAttribute("aria-expanded", "false");
        }));
    }

    const revealItems = document.querySelectorAll(".landing-reveal:not(.is-visible)");
    if (reduceMotion || !("IntersectionObserver" in window)) {
        revealItems.forEach((item) => item.classList.add("is-visible"));
    } else {
        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-visible");
                revealObserver.unobserve(entry.target);
            });
        }, { threshold: 0.12, rootMargin: "0px 0px -30px" });
        revealItems.forEach((item) => revealObserver.observe(item));
    }

    const countItems = document.querySelectorAll("[data-count]");
    const formatCount = (value) => new Intl.NumberFormat("en-US").format(value);
    const animateCount = (element) => {
        const target = Number(element.dataset.count);
        if (!Number.isFinite(target) || reduceMotion) return;
        const started = performance.now();
        const duration = 900;
        const tick = (now) => {
            const progress = Math.min((now - started) / duration, 1);
            element.textContent = formatCount(Math.round(target * (1 - Math.pow(1 - progress, 3))));
            if (progress < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    };
    if (!reduceMotion && "IntersectionObserver" in window) {
        const countObserver = new IntersectionObserver((entries) => entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            animateCount(entry.target);
            countObserver.unobserve(entry.target);
        }), { threshold: 0.8 });
        countItems.forEach((item) => countObserver.observe(item));
    }

    const parallaxRoot = document.querySelector("[data-parallax-root]");
    const finePointer = window.matchMedia("(pointer: fine) and (min-width: 992px)").matches;
    if (parallaxRoot && finePointer && !reduceMotion) {
        const layers = parallaxRoot.querySelectorAll("[data-depth]");
        parallaxRoot.addEventListener("pointermove", (event) => {
            const rect = parallaxRoot.getBoundingClientRect();
            const x = (event.clientX - rect.left) / rect.width - 0.5;
            const y = (event.clientY - rect.top) / rect.height - 0.5;
            layers.forEach((layer) => {
                const depth = Number(layer.dataset.depth || 0);
                layer.style.translate = `${x * depth * 18}px ${y * depth * 18}px`;
            });
        });
        parallaxRoot.addEventListener("pointerleave", () => layers.forEach((layer) => {
            layer.style.translate = "0 0";
        }));
    }
}());
