document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll("input[data-max-of]").forEach((input) => {
    const total = document.querySelector(`input[name="${input.dataset.maxOf}"]`);
    if (!total) return;

    const clamp = () => {
      const max = parseInt(total.value || "0", 10);
      const value = parseInt(input.value || "0", 10);
      if (!Number.isNaN(max) && !Number.isNaN(value) && value > max) {
        input.value = max;
      }
    };

    total.addEventListener("input", clamp);
    input.addEventListener("input", clamp);
  });
});
