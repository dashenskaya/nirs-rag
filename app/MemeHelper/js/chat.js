/*
 * Центральная область: сообщения, ответы с мемами, отправка запроса.
 *
 * Формат сообщений в чате:
 *   { role: 'user', text }
 *   { role: 'assistant', status: 'success', query, results: [...] }
 *   { role: 'assistant', status: 'empty',   query }
 *   { role: 'assistant', status: 'error',   query }
 */

const EXAMPLES = [
  { type: 'Ситуация', text: 'Друг прислал очень смешное видео, хочу ответить, что я угораю' },
  { type: 'Цитата из сообщения', text: '«Всё, я спать, спокойной ночи!»' },
  { type: 'Описание мема', text: 'Волк крупным планом смотрит прямо в камеру' },
];

const messagesBox = document.getElementById('messages');
const chatBox = document.getElementById('chat');
const composer = document.getElementById('composer');
const input = document.getElementById('input');
const sendButton = document.getElementById('send');

// ===== Отрисовка =====

function renderChat() {
  const messages = state.chat ? state.chat.messages : [];
  document.getElementById('chat-title').textContent = state.chat?.title || 'Новый чат';

  if (!messages.length && !state.loading) {
    messagesBox.innerHTML = emptyChatHtml();
    return;
  }

  let html = messages.map(messageHtml).join('');
  if (state.loading) html += loadingHtml();
  messagesBox.innerHTML = html;
  scrollToBottom();
}

// Пустое состояние: что умеет сервис + примеры запросов
function emptyChatHtml() {
  const examples = EXAMPLES.map(
    (ex) => `
      <button class="example" type="button" data-example="${escapeHtml(ex.text)}">
        <span class="example__type">${ex.type}</span>
        <span class="example__text">${escapeHtml(ex.text)}</span>
      </button>`
  ).join('');

  return `
    <div class="welcome">
      <img class="welcome__logo" src="images/logo.png" alt="">
      <h2 class="welcome__title">Meme Helper</h2>
      <p class="welcome__text">Опишите ситуацию, и Meme Helper подберёт 5 подходящих мемов —
        объяснит, что они значат, и подскажет, что написать.</p>
      <div class="examples">${examples}</div>
    </div>`;
}

function messageHtml(message, index) {
  if (message.role === 'user') {
    return `<div class="msg msg--user"><div class="bubble bubble--user">${escapeHtml(message.text)}</div></div>`;
  }

  let body;
  if (message.status === 'success') {
    const n = message.results.length;
    body = `
      <p class="bubble__lead">Вот ${n} ${plural(n, 'подходящий мем', 'подходящих мема', 'подходящих мемов')}:</p>
      <div class="results">${message.results.map(resultHtml).join('')}</div>`;
  } else if (message.status === 'empty') {
    body = `
      <div class="state state--empty">
        <span class="state__icon">🔍</span>
        <div>
          <p class="state__title">Подходящие мемы не найдены</p>
          <p class="state__text">Попробуйте описать ситуацию по-другому: что произошло, что вы чувствуете или кому отвечаете.</p>
        </div>
      </div>`;
  } else {
    body = `
      <div class="state state--error">
        <span class="state__icon">⚠️</span>
        <div>
          <p class="state__title">Не удалось получить рекомендации. Попробуйте ещё раз.</p>
          <button class="btn btn--small" type="button" data-retry="${index}">Повторить</button>
        </div>
      </div>`;
  }

  return `<div class="msg msg--bot"><img class="bot-avatar" src="images/logo.png" alt=""><div class="bubble bubble--bot">${body}</div></div>`;
}

// Одна карточка мема: крупная картинка сверху, под ней описание
function resultHtml(result, i) {
  const { meme } = result;
  // [изображение] в тексте показываем значком, а при копировании убираем
  const suggestion = escapeHtml(result.suggestion).replace(
    '[изображение]',
    '<span class="img-chip">мем</span>'
  );

  return `
    <article class="result">
      <div class="result__media">
        <img src="${escapeHtml(meme.image)}" alt="${escapeHtml(meme.name)}">
        <span class="result__num">№${i + 1}</span>
        <a class="result__download" href="${escapeHtml(meme.image)}" download title="Скачать мем">Скачать</a>
      </div>

      <div class="result__body">
        <h3 class="result__name">${escapeHtml(meme.name)}</h3>
        <p class="result__meta">${[meme.year, meme.relevance].filter(Boolean).map(escapeHtml).join(' · ')}</p>

        <p class="result__origin">${escapeHtml(meme.origin)}</p>

        <div class="result__block">
          <h4 class="result__label">Почему подходит</h4>
          <p>${escapeHtml(result.explanation)}</p>
        </div>

        <div class="suggest">
          <div class="suggest__head">
            <h4 class="result__label">Можно написать</h4>
            <button class="suggest__copy" type="button" data-copy="${escapeHtml(result.suggestion)}">Скопировать</button>
          </div>
          <p class="suggest__text">${suggestion}</p>
        </div>
      </div>
    </article>`;
}

function loadingHtml() {
  return `
    <div class="msg msg--bot">
      <img class="bot-avatar" src="images/logo.png" alt="">
      <div class="bubble bubble--bot bubble--loading">
        Ищу подходящие мемы<span class="dots"><i></i><i></i><i></i></span>
      </div>
    </div>`;
}

function scrollToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

// ===== Отправка запроса =====

function setLoading(loading) {
  state.loading = loading;
  sendButton.disabled = loading; // нельзя отправить второй запрос, пока ждём ответ
  input.disabled = loading;
}

// Новый пустой чат (ещё не сохранён, сохранится после первого сообщения)
function createChat() {
  return { id: 'chat_' + Date.now(), title: '', updatedAt: Date.now(), messages: [] };
}

async function sendMessage(text) {
  text = text.trim();
  if (!text || state.loading) return;

  if (!state.chat) state.chat = createChat();
  const chat = state.chat;
  if (!chat.title) chat.title = text.length > 40 ? text.slice(0, 40) + '…' : text;

  // 1. сообщение пользователя появляется в чате, 2. поле очищается
  chat.messages.push({ role: 'user', text });
  input.value = '';
  autoResize();

  // 3. показываем состояние обработки
  setLoading(true);
  renderChat();

  // 4. получаем и показываем ответ
  chat.messages.push(await ask(text));
  setLoading(false);
  await persistChat(chat);
  renderChat();
  input.focus();
}

// Запрос к «ИИ» → сообщение-ответ нужного состояния
async function ask(query) {
  try {
    const { results } = await api.searchMemes(query);
    return results.length
      ? { role: 'assistant', status: 'success', query, results }
      : { role: 'assistant', status: 'empty', query };
  } catch (e) {
    return { role: 'assistant', status: 'error', query };
  }
}

// Повторить запрос, который закончился ошибкой
async function retry(index) {
  if (state.loading) return;
  const chat = state.chat;
  const failed = chat.messages[index];
  chat.messages.splice(index, 1); // убираем сообщение об ошибке
  setLoading(true);
  renderChat();
  chat.messages.splice(index, 0, await ask(failed.query));
  setLoading(false);
  await persistChat(chat);
  renderChat();
}

// Вошедшему сохраняем чат в историю, гостю — нет
async function persistChat(chat) {
  if (!state.user) return;
  chat.updatedAt = Date.now();
  await api.saveChat(chat);
  renderSidebar();
}

// ===== Поле ввода =====

// Поле растёт по высоте вместе с текстом (до 6 строк)
function autoResize() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 160) + 'px';
}

input.addEventListener('input', autoResize);

// Enter — отправить, Shift+Enter — перенос строки
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage(input.value);
  }
});

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

// Клики внутри чата: пример запроса, «Повторить», «Скопировать текст»
messagesBox.addEventListener('click', async (event) => {
  const example = event.target.closest('[data-example]');
  if (example) {
    input.value = example.dataset.example;
    autoResize();
    input.focus();
    return;
  }

  const retryBtn = event.target.closest('[data-retry]');
  if (retryBtn) {
    retry(Number(retryBtn.dataset.retry));
    return;
  }

  const copyBtn = event.target.closest('[data-copy]');
  if (copyBtn) {
    const text = copyBtn.dataset.copy.replace('[изображение]', '').trim();
    try {
      await navigator.clipboard.writeText(text);
      showToast('Текст скопирован — осталось прикрепить мем');
    } catch (e) {
      showToast('Не получилось скопировать. Выделите текст вручную');
    }
  }
});
