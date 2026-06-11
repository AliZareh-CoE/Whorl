// Islands loader (Owner idea #19): finds [data-island] elements, reads JSON props
// from the json_script tag named by data-props, lazy-imports the island module and
// mounts it. If anything fails, the server-rendered fallback stays in place.
document.querySelectorAll("[data-island]").forEach(async (el) => {
  const name = el.dataset.island;
  if (!/^[a-z0-9-]+$/.test(name)) return;
  let props = {};
  const propsEl = document.getElementById(el.dataset.props || "");
  if (propsEl) {
    try {
      props = JSON.parse(propsEl.textContent);
    } catch (e) {
      console.error("island props unreadable:", name, e);
      return;
    }
  }
  try {
    const mod = await import(`/static/js/islands/${name}.js`);
    mod.default(el, props);
  } catch (e) {
    console.error("island failed to mount (fallback stays):", name, e);
  }
});
