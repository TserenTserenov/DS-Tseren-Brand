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

for (const mcpCopy of document.querySelectorAll(".mcp-copy")) {
  mcpCopy.addEventListener("click", async () => {
    try {
      const target = document.querySelector(`#${mcpCopy.dataset.copyTarget}`);
      await navigator.clipboard.writeText(target.textContent.trim());
      mcpCopy.textContent = mcpCopy.dataset.copied;
    } catch {
      mcpCopy.textContent = mcpCopy.dataset.error;
    }
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
        limit: "Local search only · no model calls or answer allowance used.",
        searching: "Searching the selected materials…",
        found: (count) => `${count} search results. These are sources to read, not a generated answer.`,
        answered: (count) => `Answer based on ${count} linked sources.`,
        remaining: (daily, limit, shared, reset) => `You have ${daily} of ${limit} questions left today. The shared allowance currently covers at least ${shared} more questions until ${reset} UTC.`,
        dailyLimit: "Your daily question allowance is exhausted. Here are sources to read.",
        sharedLimit: "The shared question allowance is exhausted. Here are sources to read.",
        modelUnavailable: "AI answers are temporarily unavailable. Here are sources to read.",
        none: "No matching materials found. Try another question or browse the library.",
        unavailable: "Search is temporarily unavailable. Try again or browse the library.",
        localUnavailable: "Local search is unavailable. Start the site gateway or browse the library.",
        copyResult: "Copy answer and sources",
        copied: "Copied",
        copyError: "Could not copy",
      }
    : {
        preview: "Локальный предпросмотр: поиск по выбранному открытому репозиторию без черновиков и без ИИ-модели. Вопрос уходит только на локальный сервер.",
        limit: "Только локальный поиск · без вызовов модели и расхода квоты ответов.",
        searching: "Ищу материалы в выбранной подборке…",
        found: (count) => `Найдено материалов: ${count}. Это источники для чтения, а не сгенерированный ответ.`,
        answered: (count) => `Ответ основан на ${count} ${count === 1 ? "источнике" : "источниках"} ниже.`,
        remaining: (daily, limit, shared, reset) => `Сегодня вам доступно ещё ${daily} из ${limit} запросов. Общая квота сейчас позволяет сделать не менее ${shared} запросов до ${reset} UTC.`,
        dailyLimit: "Ваш дневной лимит запросов исчерпан. Вот материалы для чтения.",
        sharedLimit: "Общая квота запросов исчерпана. Вот материалы для чтения.",
        modelUnavailable: "ИИ-ответы временно недоступны. Вот материалы для чтения.",
        none: "Подходящих материалов нет. Попробуйте другой вопрос или откройте библиотеку.",
        unavailable: "Поиск временно недоступен. Попробуйте ещё раз или откройте библиотеку.",
        localUnavailable: "Локальный поиск недоступен. Запустите сервер сайта или откройте библиотеку.",
        copyResult: "Копировать ответ и источники",
        copied: "Скопировано",
        copyError: "Не удалось скопировать",
      };
  const results = document.createElement("ul");
  results.className = "ask-results";
  results.hidden = true;
  status.after(results);
  const answer = document.createElement("p");
  answer.className = "ask-answer";
  answer.hidden = true;
  status.after(answer);
  const copyResult = document.createElement("button");
  copyResult.type = "button";
  copyResult.className = "ask-copy";
  copyResult.setAttribute("aria-label", copy.copyResult);
  copyResult.title = copy.copyResult;
  copyResult.innerHTML = `
    <svg class="ask-copy-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="8" y="8" width="12" height="12" rx="2"></rect>
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path>
    </svg>
    <svg class="ask-copied-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="m5 12 4 4L19 6"></path>
    </svg>`;
  copyResult.hidden = true;
  results.after(copyResult);
  const copyFeedback = document.createElement("span");
  copyFeedback.className = "ask-copy-feedback";
  copyFeedback.setAttribute("role", "status");
  copyResult.after(copyFeedback);
  const resetCopy = () => {
    copyResult.hidden = true;
    copyResult.dataset.state = "ready";
    copyFeedback.textContent = "";
  };
  copyResult.addEventListener("click", async () => {
    const parts = [];
    if (!answer.hidden) parts.push(answer.textContent.trim());
    for (const [index, row] of [...results.children].entries()) {
      const link = row.querySelector("a");
      const snippet = row.querySelector("p")?.textContent.trim();
      if (link) parts.push(`[${index + 1}] ${link.textContent.trim()}\n${link.href}${snippet ? `\n${snippet}` : ""}`);
    }
    try {
      await navigator.clipboard.writeText(parts.join("\n\n"));
      copyResult.dataset.state = "copied";
      copyFeedback.textContent = copy.copied;
    } catch {
      copyResult.dataset.state = "error";
      copyFeedback.textContent = copy.copyError;
    }
  });
  if (localPreview) {
    document.querySelector("#ask-preview").textContent = copy.preview;
    document.querySelector("#ask-limit").textContent = copy.limit;
  }
  for (const example of askForm.querySelectorAll("[data-question]")) {
    example.disabled = false;
    example.addEventListener("click", () => {
      question.value = example.textContent.trim();
      status.hidden = true;
      answer.hidden = true;
      results.hidden = true;
      results.replaceChildren();
      resetCopy();
      question.focus();
    });
  }
  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = question.value.trim();
    results.hidden = true;
    results.replaceChildren();
    answer.hidden = true;
    answer.textContent = "";
    resetCopy();
    status.hidden = false;
    if (!value) {
      status.textContent = askForm.dataset.empty;
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
      if (data.mode === "answer" && typeof data.answer === "string") {
        answer.textContent = data.answer;
        answer.hidden = false;
        status.textContent = copy.answered(data.results.length);
        if (Number.isInteger(data.daily_requests_remaining) && data.daily_requests_remaining >= 0
          && Number.isInteger(data.daily_request_limit) && data.daily_request_limit > 0
          && Number.isInteger(data.shared_requests_guaranteed) && data.shared_requests_guaranteed >= 0
          && /^\d{4}-\d{2}-\d{2}T00:00:00\.000Z$/.test(data.resets_at)) {
          status.textContent += ` ${copy.remaining(data.daily_requests_remaining, data.daily_request_limit, data.shared_requests_guaranteed, data.resets_at.slice(0, 10))}`;
        }
      } else if (!data.results.length) {
        status.textContent = copy.none;
      } else if (data.reason === "visitor_limit") {
        status.textContent = copy.dailyLimit;
      } else if (data.reason === "budget_limit") {
        status.textContent = copy.sharedLimit;
      } else if (["model_unavailable", "quota_unavailable"].includes(data.reason)) {
        status.textContent = copy.modelUnavailable;
      } else {
        status.textContent = copy.found(data.results.length);
      }
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
      copyResult.hidden = answer.hidden && results.hidden;
    } catch {
      status.textContent = localPreview ? copy.localUnavailable : copy.unavailable;
    } finally {
      submit.disabled = false;
    }
  });
  submit.disabled = false;
}
