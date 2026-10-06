const search = document.querySelector("#library-search");
if (search) {
  const entries = [...document.querySelectorAll("[data-search]")];
  const count = document.querySelector("#search-count");
  const empty = document.querySelector(".empty-search");
  search.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const entry of entries) {
      entry.hidden = !entry.dataset.search.toLocaleLowerCase().includes(query);
      if (!entry.hidden) visible += 1;
    }
    count.textContent =
      document.documentElement.lang === "en"
        ? `${visible} found`
        : `Найдено: ${visible}`;
    empty.hidden = visible > 0;
  });
}

for (const player of document.querySelectorAll("[data-video]")) {
  player.querySelector("button").addEventListener("click", () => {
    if (!/^[\w-]{11}$/.test(player.dataset.video)) return;
    const frame = document.createElement("iframe");
    frame.src = `https://www.youtube-nocookie.com/embed/${player.dataset.video}?autoplay=1`;
    frame.title = player.dataset.title;
    frame.allow =
      "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture";
    frame.allowFullscreen = true;
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    player.replaceChildren(frame);
  });
}
