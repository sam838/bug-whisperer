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

// Before/after compare slider: dragging moves a clip-path wipe (no layout, GPU only).
document.addEventListener("input", (event) => {
  const range = event.target.closest(".compare-range");
  if (!range) return;
  range.closest("[data-compare]").style.setProperty("--pos", `${range.value}%`);
});

// While Kane or Claude is working, refresh the live part of a case page.
// Only what is NEW animates: steps that weren't there before, and a stamp whose words changed.
// Without this, everything would re-animate every 2 seconds.
const live = document.getElementById("live");
if (live) {
  const isActive = () => live.querySelector(".live-root")?.dataset.active === "true";
  const stampText = () => live.querySelector(".verdict .stamp")?.textContent.trim() || "";
  const tick = async () => {
    if (!isActive()) return;
    try {
      const response = await fetch(live.dataset.url, { cache: "no-store" });
      if (response.ok) {
        const stepsBefore = live.querySelectorAll(".steps.live li").length;
        const stampBefore = stampText();
        live.innerHTML = await response.text();
        const root = live.querySelector(".live-root");
        if (root && stampText() === stampBefore) root.classList.add("polled");
        live.querySelectorAll(".steps.live li").forEach((li, i) => {
          if (i >= stepsBefore) li.classList.add("new");
        });
      }
    } catch {
      /* try again next tick */
    }
    setTimeout(tick, 2000);
  };
  setTimeout(tick, 2000);
}
