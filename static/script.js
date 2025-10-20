// Optional: add animations
document.addEventListener("DOMContentLoaded", () => {
    const flashes = document.querySelectorAll(".flash");
    flashes.forEach(f => {
        setTimeout(() => { f.style.opacity = 0; }, 3000);
    });
});
