(() => {
  const dialog = document.querySelector('#addMealDialog');
  document.querySelectorAll('[data-open-add]').forEach(button => button.addEventListener('click', () => {
    const [date, type] = button.dataset.openAdd.split('|');
    document.querySelector('#dialogPlanDate').value = date;
    document.querySelector('#dialogMealType').value = type;
    dialog?.showModal();
  }));
  const sourceType = document.querySelector('#sourceType');
  const filterSources = () => document.querySelectorAll('#sourceId option').forEach(option => { option.hidden = option.dataset.kind !== sourceType?.value; });
  sourceType?.addEventListener('change', filterSources); filterSources();
  document.querySelectorAll('[data-toggle-panel]').forEach(button => button.addEventListener('click', () => {
    const panel = document.getElementById(button.dataset.togglePanel); panel.hidden = !panel.hidden; if (!panel.hidden) panel.querySelector('input')?.focus();
  }));
  document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', event => { if (!window.confirm(form.dataset.confirm)) event.preventDefault(); }));
  document.querySelectorAll('[data-loading-form]').forEach(form => form.addEventListener('submit', () => { form.classList.add('is-loading'); form.querySelector('button').disabled = true; }));
})();
