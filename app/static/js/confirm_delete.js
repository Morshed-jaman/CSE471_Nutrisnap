document.addEventListener('click', function (event) {
    const target = event.target;
    if (!target.matches('[data-confirm-delete]')) {
        return;
    }

    const message = target.getAttribute('data-confirm-delete') || 'Are you sure you want to delete this item?';
    if (!window.confirm(message)) {
        event.preventDefault();
    }
});
