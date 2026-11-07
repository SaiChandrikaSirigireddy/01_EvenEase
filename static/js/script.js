document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".menu-toggle");
  const nav = document.querySelector(".nav-links");
  if (toggle) toggle.addEventListener("click", () => nav.classList.toggle("open"));

  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => { if (el.isConnected) el.remove(); }, 5000);
  });
});
