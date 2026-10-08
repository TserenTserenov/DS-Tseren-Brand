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

const askForm = document.querySelector(".ask-form");
if (askForm) {
  const question = askForm.querySelector("textarea");
  const status = askForm.querySelector(".ask-status");
  const submit = askForm.querySelector('[type="submit"]');
  const localPreview = ["127.0.0.1", "localhost"].includes(location.hostname);
  const english = document.documentElement.lang === "en";
  const copy = english
    ? {
        preview: "Local preview: search over the selected public repository, excluding drafts. Most materials are in Russian. No AI model is used. Your question is sent only to the local server.",
        limit: "Local search only · no model calls or paid quota.",
        searching: "Searching the selected materials…",
        found: (count) => `${count} search results. These are sources to read, not a generated answer.`,
        none: "No matching materials found. Try another question or browse the library.",
        unavailable: "Local search is unavailable. Start the site gateway or browse the library.",
      }
    : {
        preview: "Локальный предпросмотр: поиск по выбранному открытому репозиторию без черновиков и без ИИ-модели. Вопрос уходит только на локальный сервер.",
        limit: "Только локальный поиск · без вызовов модели и платной квоты.",
        searching: "Ищу материалы в выбранной подборке…",
        found: (count) => `Найдено материалов: ${count}. Это источники для чтения, а не сгенерированный ответ.`,
        none: "Подходящих материалов нет. Попробуйте другой вопрос или откройте библиотеку.",
        unavailable: "Локальный поиск недоступен. Запустите сервер сайта или откройте библиотеку.",
      };
  const results = document.createElement("ul");
  results.className = "ask-results";
  results.hidden = true;
  status.after(results);
  if (localPreview) {
    document.querySelector("#ask-preview").textContent = copy.preview;
    document.querySelector("#ask-limit").textContent = copy.limit;
  }
  for (const example of askForm.querySelectorAll("[data-question]")) {
    example.disabled = false;
    example.addEventListener("click", () => {
      question.value = example.textContent.trim();
      status.hidden = true;
      results.hidden = true;
      results.replaceChildren();
      question.focus();
    });
  }
  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = question.value.trim();
    results.hidden = true;
    results.replaceChildren();
    status.hidden = false;
    if (!value) {
      status.textContent = askForm.dataset.empty;
      return;
    }
    if (!localPreview) {
      status.textContent = askForm.dataset.unavailable;
      return;
    }
    submit.disabled = true;
    status.textContent = copy.searching;
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: value }),
      });
      if (!response.ok) throw new Error(`Search returned ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.results)) throw new Error("Invalid search response");
      status.textContent = data.results.length ? copy.found(data.results.length) : copy.none;
      for (const item of data.results) {
        if (typeof item.title !== "string" || typeof item.text !== "string" || typeof item.url !== "string") continue;
        if (!item.url.startsWith("https://github.com/")) continue;
        const row = document.createElement("li");
        const link = document.createElement("a");
        link.href = item.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = item.title;
        const snippet = document.createElement("p");
        snippet.textContent = item.text;
        row.append(link, snippet);
        results.append(row);
      }
      results.hidden = results.childElementCount === 0;
    } catch {
      status.textContent = copy.unavailable;
    } finally {
      submit.disabled = false;
    }
  });
  submit.disabled = false;
}
