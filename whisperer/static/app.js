// Example complaints fill the form.
document.querySelectorAll("[data-example]").forEach((chip) => {
  chip.addEventListener("click", () => {
    const box = document.querySelector("textarea[name=report]");
    box.value = chip.dataset.example;
    box.focus();
  });
});

// Copy buttons (event delegation, because the live part is replaced while polling).
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const text = document.getElementById(button.dataset.copy)?.innerText || "";
  try {
    await navigator.clipboard.writeText(text);
    const label = button.textContent;
    button.textContent = "Copied ✓";
    setTimeout(() => (button.textContent = label), 1500);
  } catch {
    /* clipboard not allowed: the text is on the page to copy by hand */
  }
});

// While Kane or Claude is working, refresh the live part of a report page.
const live = document.getElementById("live");
if (live) {
  const isActive = () => live.querySelector(".live-root")?.dataset.active === "true";
  const tick = async () => {
    if (!isActive()) return;
    try {
      const response = await fetch(live.dataset.url, { cache: "no-store" });
      if (response.ok) live.innerHTML = await response.text();
    } catch {
      /* try again next tick */
    }
    setTimeout(tick, 2000);
  };
  setTimeout(tick, 2000);
}
