/*
 * Данные для админ-панели (admin.html).
 *
 * Сейчас всё считается в браузере по журналу запросов, который пишет api.searchMemes,
 * плюс один раз добавляются демо-данные за неделю, чтобы страница не была пустой.
 * Когда будет бэкенд, меняем содержимое функций на fetch('/api/admin/...').
 *
 * Чтобы посмотреть состояние ошибки, откройте admin.html?error=1
 */
const adminApi = (() => {
  const KEYS = {
    events: 'memehelper_events',
    demo: 'memehelper_events_demo',      // демо-данные уже добавлены
    hidden: 'memehelper_hidden_queries', // id запросов, удалённых из списка «без результатов»
  };
  const DAY = 24 * 60 * 60 * 1000;

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
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function startOfToday() {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d.getTime();
  }

  // ===== Демо-данные за последние 7 дней =====
  function addDemoData() {
    if (read(KEYS.demo, false)) return;

    let seed = 7; // свой генератор случайных чисел, чтобы данные всегда были одинаковые
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const pick = (arr) => arr[Math.floor(rnd() * arr.length)];

    const perDay = [34, 41, 28, 52, 47, 61, 19]; // от 6 дней назад до сегодня
    const guests = ['guest:a1', 'guest:b2', 'guest:c3', 'guest:d4', 'guest:e5', 'guest:f6', 'guest:g7', 'guest:h8', 'guest:i9', 'guest:j10', 'guest:k11'];
    const users = ['user:masha', 'user:petya', 'user:lena', 'user:nikita', 'user:dasha', 'user:vika'];
    const okQueries = [
      { q: 'Друг прислал очень смешное видео', memes: ['okno-smeshnoe'] },
      { q: 'Хочу ответить на шутку, что я угораю', memes: ['okno-smeshnoe'] },
      { q: 'Всё, я спать, спокойной ночи!', memes: ['volk-na-krayu'] },
      { q: 'Что пожелать подруге перед сном', memes: ['volk-na-krayu'] },
      { q: 'Смешная шутка перед сном', memes: ['okno-smeshnoe', 'volk-na-krayu'] },
    ];
    const emptyQueries = [
      'мем про то, что сломался принтер',
      'ответ начальнику на «надо поговорить»',
      'мем про дождь в выходные',
      'что ответить на «ты где?»',
      'грустный пельмень',
      'мем про сдачу курсовой в последний день',
      'реакция на спойлер к сериалу',
      'мем про пробки утром',
      'когда мама звонит в 7 утра',
      'кот, который не хочет работать',
    ];

    const events = [];
    const today = startOfToday();
    perDay.forEach((count, i) => {
      const dayStart = today - (6 - i) * DAY;
      const dayLength = i === 6 ? Math.max(Date.now() - today, 1) : DAY;
      for (let n = 0; n < count; n++) {
        const at = dayStart + Math.floor(rnd() * dayLength);
        const who = rnd() < 0.6 ? pick(guests) : pick(users);
        const r = rnd();
        let ev;
        if (r < 0.04) ev = { query: pick(okQueries).q, status: 'error', memeIds: [] };
        else if (r < 0.18) ev = { query: pick(emptyQueries), status: 'empty', memeIds: [] };
        else {
          const ok = pick(okQueries);
          ev = { query: ok.q, status: 'success', memeIds: ok.memes };
        }
        events.push({ id: `demo_${i}_${n}`, at, who, ...ev });
      }
    });

    const existing = read(KEYS.events, []);
    write(KEYS.events, [...events, ...existing].sort((a, b) => a.at - b.at));
    write(KEYS.demo, true);
  }

  // Доступ только для администратора
  async function requireAdmin() {
    const user = await api.getCurrentUser();
    if (!user) throw new Error('UNAUTHORIZED');
    if (user.role !== 'admin') throw new Error('FORBIDDEN');
    if (new URLSearchParams(location.search).has('error')) throw new Error('Демо-ошибка загрузки');
    addDemoData();
    return user;
  }

  /*
   * GET /api/admin/stats?period=day|week
   * → { period, total, byDay, users: { guests, registered }, empty, errors }
   */
  async function getStats(period) {
    await wait(500);
    await requireAdmin();

    const today = startOfToday();
    const weekStart = today - 6 * DAY;
    const all = read(KEYS.events, []);
    const inPeriod = all.filter((e) => e.at >= (period === 'day' ? today : weekStart));
    const inWeek = all.filter((e) => e.at >= weekStart);

    // По дням — только для недели
    const byDay = Array.from({ length: 7 }, (_, i) => {
      const from = weekStart + i * DAY;
      return { date: from, count: inWeek.filter((e) => e.at >= from && e.at < from + DAY).length };
    });

    // Активные пользователи за неделю: уникальные гости и уникальные зарегистрированные
    const who = new Set(inWeek.map((e) => e.who));
    const guests = [...who].filter((w) => w.startsWith('guest:')).length;

    return {
      period,
      total: inPeriod.length,
      byDay,
      users: { guests, registered: who.size - guests },
      empty: inPeriod.filter((e) => e.status === 'empty').length,
      errors: inPeriod.filter((e) => e.status === 'error').length,
    };
  }

  /*
   * GET /api/admin/memes
   * → { top: [{ id, name, image, shows }], dead: [{ id, name, image }] }
   */
  async function getMemeStats() {
    await wait(400);
    await requireAdmin();

    const shows = {};
    read(KEYS.events, []).forEach((e) => (e.memeIds || []).forEach((id) => (shows[id] = (shows[id] || 0) + 1)));
    const info = (m) => ({ id: m.id, name: m.name, image: m.image });

    return {
      top: MEMES.filter((m) => shows[m.id])
        .map((m) => ({ ...info(m), shows: shows[m.id] }))
        .sort((a, b) => b.shows - a.shows),
      dead: MEMES.filter((m) => !shows[m.id]).map(info),
    };
  }

  // GET /api/admin/empty-queries — запросы без результатов, новые сверху (ошибки сюда не входят)
  async function getEmptyQueries() {
    await wait(400);
    await requireAdmin();
    const hidden = new Set(read(KEYS.hidden, []));
    return read(KEYS.events, [])
      .filter((e) => e.status === 'empty' && !hidden.has(e.id))
      .sort((a, b) => b.at - a.at)
      .map((e) => ({ id: e.id, query: e.query, at: e.at }));
  }

  // DELETE /api/admin/empty-queries/:id — убрать запись из списка (статистика не меняется)
  async function deleteEmptyQuery(id) {
    await requireAdmin();
    write(KEYS.hidden, [...read(KEYS.hidden, []), id]);
  }

  return { getStats, getMemeStats, getEmptyQueries, deleteEmptyQuery };
})();
