/*
 * «Слой данных» — ВСЯ связь сайта с бэкендом идёт только через эти функции.
 *
 * Сейчас это заглушки: пользователи и чаты лежат в localStorage браузера,
 * а «ИИ» подбирает мемы по ключевым словам из js/data.js.
 *
 * Когда бэкенд Даши будет готов, меняем ТОЛЬКО содержимое функций ниже
 * на fetch('/api/...'). Остальной код сайта трогать не придётся.
 * Над каждой функцией подписан предполагаемый адрес API.
 *
 * Все функции async — как настоящие запросы к серверу.
 */
const api = (() => {
  const KEYS = {
    users: 'memehelper_users',     // «таблица» пользователей
    session: 'memehelper_session', // логин того, кто сейчас вошёл
    chats: 'memehelper_chats',     // { [login]: [чат, чат, ...] }
    events: 'memehelper_events',   // журнал запросов для админки
    guest: 'memehelper_guest',     // id гостя в этом браузере
  };

  // --- безопасная работа с localStorage ---
  function read(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }
  function write(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  // Имитация задержки сети
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // Отдаём наружу пользователя без пароля
  function publicUser(user) {
    return user
      ? { login: user.login, nickname: user.nickname, avatar: user.avatar || null, role: user.role || 'user' }
      : null;
  }

  // Демо-администратор: логин admin, пароль admin123.
  // На бэкенде роль хранится в базе, а не создаётся в браузере.
  function ensureAdmin() {
    const users = read(KEYS.users, []);
    if (!users.some((u) => u.login === 'admin')) {
      write(KEYS.users, [...users, { login: 'admin', nickname: 'Админ', password: 'admin123', avatar: null, role: 'admin' }]);
    }
  }
  try {
    ensureAdmin();
  } catch (e) {
    /* localStorage недоступен — просто без админа */
  }

  // ===================== Пользователь =====================

  // GET /api/me
  async function getCurrentUser() {
    const login = read(KEYS.session, null);
    if (!login) return null;
    const user = read(KEYS.users, []).find((u) => u.login === login);
    return publicUser(user);
  }

  // POST /api/auth/login
  async function login(loginValue, password) {
    await wait(300);
    const user = read(KEYS.users, []).find((u) => u.login === loginValue.trim().toLowerCase());
    // Заглушка хранит пароль открытым текстом — так можно ТОЛЬКО в прототипе.
    // Настоящий бэкенд хранит хеш пароля.
    if (!user || user.password !== password) {
      throw new Error('Неверный логин или пароль');
    }
    write(KEYS.session, user.login);
    return publicUser(user);
  }

  // POST /api/auth/register
  async function register({ login: loginValue, nickname, password }) {
    await wait(300);
    const loginNorm = loginValue.trim().toLowerCase();
    if (!/^[a-z0-9_.-]{3,20}$/.test(loginNorm)) {
      throw new Error('Логин: от 3 до 20 символов — латиница, цифры, точка, _ или -');
    }
    if (password.length < 6) throw new Error('Пароль должен быть не короче 6 символов');

    const users = read(KEYS.users, []);
    if (users.some((u) => u.login === loginNorm)) {
      throw new Error('Пользователь с таким логином уже есть');
    }
    const user = { login: loginNorm, nickname: nickname.trim() || loginNorm, password, avatar: null, role: 'user' };
    write(KEYS.users, [...users, user]);
    write(KEYS.session, user.login);
    return publicUser(user);
  }

  // POST /api/auth/logout
  async function logout() {
    localStorage.removeItem(KEYS.session);
  }

  // PATCH /api/me — меняем никнейм и/или фото (avatar — картинка в виде data:URL или null)
  async function updateProfile({ nickname, avatar }) {
    await wait(200);
    const login = read(KEYS.session, null);
    const users = read(KEYS.users, []);
    const user = users.find((u) => u.login === login);
    if (!user) throw new Error('UNAUTHORIZED');
    if (!nickname.trim()) throw new Error('Никнейм не может быть пустым');
    user.nickname = nickname.trim();
    user.avatar = avatar;
    try {
      write(KEYS.users, users);
    } catch (e) {
      throw new Error('Фото слишком большое. Попробуйте другое.');
    }
    return publicUser(user);
  }

  // ===================== История чатов =====================
  // Чат: { id, title, updatedAt, messages: [...] }

  async function myLogin() {
    const user = await getCurrentUser();
    if (!user) throw new Error('UNAUTHORIZED');
    return user.login;
  }

  // GET /api/chats — список без сообщений, новые сверху
  async function listChats() {
    const login = await myLogin();
    const chats = read(KEYS.chats, {})[login] || [];
    return chats
      .map(({ id, title, updatedAt }) => ({ id, title, updatedAt }))
      .sort((a, b) => b.updatedAt - a.updatedAt);
  }

  // GET /api/chats/:id
  async function getChat(id) {
    const login = await myLogin();
    const chats = read(KEYS.chats, {})[login] || [];
    return chats.find((c) => c.id === id) || null;
  }

  // PUT /api/chats/:id — создать или обновить чат
  async function saveChat(chat) {
    const login = await myLogin();
    const all = read(KEYS.chats, {});
    const chats = all[login] || [];
    const index = chats.findIndex((c) => c.id === chat.id);
    if (index === -1) chats.push(chat);
    else chats[index] = chat;
    all[login] = chats;
    write(KEYS.chats, all);
    return chat;
  }

  // DELETE /api/chats/:id
  async function deleteChat(id) {
    const login = await myLogin();
    const all = read(KEYS.chats, {});
    all[login] = (all[login] || []).filter((c) => c.id !== id);
    write(KEYS.chats, all);
  }

  // ===================== Подбор мемов (RAG) =====================

  function normalize(str) {
    return String(str).toLowerCase().replace(/ё/g, 'е');
  }

  /*
   * POST /api/search  { query }  →  { results: [{ meme, explanation, suggestion }] }
   *   meme — данные мема из базы: { id, name, image, year, origin, relevance }
   *
   * ЗАГЛУШКА вместо настоящего RAG. Настоящий пайплайн (бэкенд + база):
   *   1. векторный поиск находит 10–20 кандидатов по смыслу запроса;
   *   2. LLM выбирает до 5 лучших и пишет объяснение и текст сообщения.
   * Здесь вместо этого — совпадение по ключевым словам и готовые шаблоны текста.
   *
   * Чтобы показать состояние ошибки, напишите в чат слово «ошибка».
   */
  async function searchMemes(query) {
    await wait(1200);

    const q = normalize(query);
    if (q.includes('ошибка')) {
      await logEvent(query, 'error', []);
      throw new Error('Демо-ошибка сервера');
    }

    const scored = MEMES.map((meme) => ({
      meme,
      score: meme.keywords.filter((k) => q.includes(normalize(k))).length,
    }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);

    await logEvent(query, scored.length ? 'success' : 'empty', scored.map((x) => x.meme.id));

    return {
      results: scored.map(({ meme }, i) => ({
        meme: {
          id: meme.id,
          name: meme.name,
          image: meme.image,
          year: meme.year,
          origin: meme.origin,
          relevance: meme.relevance,
        },
        explanation: `${meme.meaning} В вашей ситуации подходит, потому что ${meme.fit}.`,
        suggestion: meme.replies[i % meme.replies.length],
      })),
    };
  }

  /*
   * Журнал запросов для админ-панели: что спросили, чем закончилось, какие мемы показали.
   * На настоящем сайте его ведёт бэкенд сам, фронту ничего делать не нужно.
   */
  async function logEvent(query, status, memeIds) {
    const user = await getCurrentUser();
    let who = user ? 'user:' + user.login : read(KEYS.guest, null);
    if (!who) {
      who = 'guest:' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      write(KEYS.guest, who);
    }
    const events = read(KEYS.events, []);
    events.push({ id: 'ev_' + Date.now(), query, status, memeIds, at: Date.now(), who });
    try {
      write(KEYS.events, events.slice(-3000)); // храним последние 3000
    } catch (e) {
      /* место кончилось — не страшно для демо */
    }
  }

  return {
    getCurrentUser, login, register, logout, updateProfile,
    listChats, getChat, saveChat, deleteChat,
    searchMemes,
  };
})();
