(function () {
    "use strict";

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const menuButton = document.querySelector(".premium-menu-toggle");
    const menu = document.querySelector(".premium-nav-links");
    const navWrap = document.querySelector(".premium-nav-wrap");
    const motionToggle = document.querySelector(".motion-toggle");

    const resetParallax = () => document.querySelectorAll("[data-depth]").forEach((layer) => {
        layer.style.translate = "0 0";
        layer.style.scale = "1";
    });

    const setMotionPaused = (paused) => {
        document.body.classList.toggle("motion-paused", paused);
        if (!motionToggle) return;
        motionToggle.setAttribute("aria-pressed", String(paused));
        motionToggle.querySelector(".motion-symbol").textContent = paused ? "▶" : "Ⅱ";
        motionToggle.querySelector("span:last-child").textContent = paused ? "Play motion" : "Pause motion";
        if (paused) resetParallax();
    };

    if (navWrap) {
        const updateNavigation = () => navWrap.classList.toggle("is-scrolled", window.scrollY > 24);
        updateNavigation();
        window.addEventListener("scroll", updateNavigation, { passive: true });
    }

    if (motionToggle) {
        let savedPause = false;
        try { savedPause = sessionStorage.getItem("nutrisnap-motion-paused") === "true"; } catch (_error) { savedPause = false; }
        setMotionPaused(savedPause);
        motionToggle.addEventListener("click", () => {
            const paused = !document.body.classList.contains("motion-paused");
            setMotionPaused(paused);
            try { sessionStorage.setItem("nutrisnap-motion-paused", String(paused)); } catch (_error) { /* Session storage is optional. */ }
        });
    }

    if (menuButton && menu) {
        const closeMenu = (restoreFocus = false) => {
            menu.classList.remove("is-open");
            menuButton.setAttribute("aria-expanded", "false");
            document.body.classList.remove("menu-open");
            if (restoreFocus) menuButton.focus();
        };
        menuButton.addEventListener("click", () => {
            const isOpen = menu.classList.toggle("is-open");
            menuButton.setAttribute("aria-expanded", String(isOpen));
            document.body.classList.toggle("menu-open", isOpen);
        });
        menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => closeMenu()));
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && menu.classList.contains("is-open")) closeMenu(true);
        });
        document.addEventListener("pointerdown", (event) => {
            if (menu.classList.contains("is-open") && !menu.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
        });
        window.addEventListener("resize", () => { if (window.innerWidth >= 992) closeMenu(); }, { passive: true });
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
            if (document.body.classList.contains("motion-paused")) return;
            const rect = parallaxRoot.getBoundingClientRect();
            const x = (event.clientX - rect.left) / rect.width - 0.5;
            const y = (event.clientY - rect.top) / rect.height - 0.5;
            layers.forEach((layer) => {
                const depth = Number(layer.dataset.depth || 0);
                layer.style.translate = `${x * depth * 18}px ${y * depth * 18}px`;
                if (layer.classList.contains("meal-stage")) layer.style.scale = String(1 + Math.hypot(x, y) * 0.018);
            });
        });
        parallaxRoot.addEventListener("pointerleave", resetParallax);
    }
}());
