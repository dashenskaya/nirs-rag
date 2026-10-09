/*
 * Админ-панель: слева аналитика, справа списки мемов и запросов без результатов.
 * Состояния страницы: загрузка → данные | ошибка (с «Повторить») | нет доступа.
 */

const adminBox = document.getElementById('admin');
let period = 'week'; // 'day' | 'week'

// ===== Общие кусочки =====

function card(title, body, extra = '') {
  return `
    <section class="a-card">
      <div class="a-card__head">
        <h2 class="a-card__title">${title}</h2>
        ${extra}
      </div>
      ${body}
    </section>`;
}

function emptyNote(text) {
  return `<p class="a-empty">${text}</p>`;
}

function percent(part, total) {
  return total ? Math.round((part / total) * 1000) / 10 : 0; // одна цифра после запятой
}

function formatDateTime(ts) {
  return new Date(ts).toLocaleString('ru-RU', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

function formatDay(ts) {
  const d = new Date(ts);
  const wd = d.toLocaleDateString('ru-RU', { weekday: 'short' });
  return `${wd} ${d.getDate()}`;
}

// ===== Состояния страницы =====

function renderLoading() {
  const skel = (h) => `<div class="a-card a-skeleton" style="height:${h}px"></div>`;
  adminBox.innerHTML = `
    <div class="admin__col">${skel(150)}${skel(130)}${skel(110)}${skel(110)}${skel(260)}</div>
    <div class="admin__col">${skel(220)}${skel(160)}${skel(360)}</div>
    <p class="a-loading-text">Загружаем аналитику…</p>`;
}

function renderError() {
  adminBox.innerHTML = `
    <div class="a-plate a-plate--error">
      <p class="a-plate__title">Не удалось получить данные</p>
      <p class="a-plate__text">Проверьте соединение и попробуйте ещё раз.</p>
      <button class="btn" type="button" id="retry">Повторить</button>
    </div>`;
  document.getElementById('retry').addEventListener('click', load);
}

function renderForbidden() {
  adminBox.innerHTML = `
    <div class="a-plate">
      <p class="a-plate__title">Доступ к данной странице вам не выдан. Админ бы вас могнул.</p>
    </div>`;
}

// ===== Левая часть: аналитика =====

function requestsCard(stats) {
  const toggle = `
    <div class="a-toggle" role="group" aria-label="Период">
      <button type="button" data-period="day" class="${period === 'day' ? 'is-active' : ''}">День</button>
      <button type="button" data-period="week" class="${period === 'week' ? 'is-active' : ''}">Неделя</button>
    </div>`;
  const body = stats.total
    ? `<p class="a-big">${stats.total}</p>
       <p class="a-sub">${period === 'day' ? 'за сегодня' : 'за последние 7 дней'}</p>`
    : emptyNote(period === 'day' ? 'Сегодня запросов пока не было' : 'За неделю запросов не было');
  return card('Количество запросов', body, toggle);
}

function usersCard(users) {
  const body =
    users.guests || users.registered
      ? `<div class="a-pair">
           <div class="a-field"><span class="a-field__label">Гости</span><span class="a-field__value">${users.guests}</span></div>
           <div class="a-field"><span class="a-field__label">Зарегистрированные</span><span class="a-field__value">${users.registered}</span></div>
         </div>`
      : emptyNote('За последнюю неделю активности не было');
  return card('Активность пользователей', `<p class="a-sub a-sub--top">за последние 7 дней</p>${body}`);
}

function rateCard(title, part, total, kind) {
  if (!total) return card(title, emptyNote('Нет запросов за выбранный период'));
  const p = percent(part, total);
  return card(
    title,
    `<p class="a-big">${p.toLocaleString('ru-RU')}&nbsp;%</p>
     <div class="a-meter a-meter--${kind}"><span style="width:${Math.max(p, part ? 1 : 0)}%"></span></div>
     <p class="a-sub">${part} из ${total} запросов</p>`
  );
}

// График запросов по дням (только для недели): столбики одного цвета, подсказка при наведении
function chartCard(byDay) {
  const max = Math.max(...byDay.map((d) => d.count));
  if (!max) return card('Запросы по дням', emptyNote('За неделю запросов не было'));

  const W = 640, H = 220, top = 24, bottom = 30, gap = 18;
  const barW = (W - gap * (byDay.length - 1)) / byDay.length;
  const scale = (H - top - bottom) / max;
  const maxIndex = byDay.findIndex((d) => d.count === max);

  const bars = byDay.map((d, i) => {
    const x = i * (barW + gap);
    const h = Math.max(d.count * scale, d.count ? 4 : 0);
    const y = H - bottom - h;
    // скругление только сверху: path вместо rect
    const r = Math.min(4, h);
    const path = h
      ? `M${x},${H - bottom} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${H - bottom} Z`
      : '';
    return `
      <g class="a-bar" data-tip="${formatDay(d.date)}: ${d.count} ${plural(d.count, 'запрос', 'запроса', 'запросов')}">
        <rect x="${x}" y="${top}" width="${barW}" height="${H - top - bottom}" fill="transparent"></rect>
        <path d="${path}"></path>
        ${i === maxIndex ? `<text class="a-bar__value" x="${x + barW / 2}" y="${y - 8}">${d.count}</text>` : ''}
        <text class="a-bar__label" x="${x + barW / 2}" y="${H - 8}">${formatDay(d.date)}</text>
      </g>`;
  }).join('');

  return card(
    'Запросы по дням',
    `<div class="a-chart">
       <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Количество запросов по дням за неделю">
         <line class="a-chart__base" x1="0" x2="${W}" y1="${H - bottom}" y2="${H - bottom}"></line>
         ${bars}
       </svg>
       <div class="a-tip" hidden></div>
     </div>`
  );
}

function renderLeft(stats) {
  return [
    requestsCard(stats),
    usersCard(stats.users),
    rateCard('Доля ответов «Не найдено»', stats.empty, stats.total, 'accent'),
    rateCard('Доля технических ошибок', stats.errors, stats.total, 'danger'),
    period === 'week' ? chartCard(stats.byDay) : '',
  ].join('');
}

// ===== Правая часть: списки =====

function topMemesCard(top) {
  const max = top[0]?.shows || 1;
  const body = top.length
    ? `<ul class="a-list">${top.map((m) => `
        <li class="a-row">
          <img class="a-thumb" src="${escapeHtml(m.image)}" alt="">
          <div class="a-row__main">
            <span class="a-row__name">${escapeHtml(m.name)}</span>
            <span class="a-row__bar"><span style="width:${(m.shows / max) * 100}%"></span></span>
          </div>
          <span class="a-row__count">${m.shows} ${plural(m.shows, 'показ', 'показа', 'показов')}</span>
        </li>`).join('')}</ul>`
    : emptyNote('Мемы ещё ни разу не показывались');
  return card('Наиболее часто показываемые мемы', body);
}

function deadMemesCard(dead) {
  const body = dead.length
    ? `<ul class="a-list">${dead.map((m) => `
        <li class="a-row">
          <img class="a-thumb" src="${escapeHtml(m.image)}" alt="">
          <span class="a-row__name">${escapeHtml(m.name)}</span>
        </li>`).join('')}</ul>`
    : emptyNote('Таких нет: каждый мем хотя бы раз попал в выдачу');
  return card('«Мёртвые» мемы', `<p class="a-sub a-sub--top">ни разу не попадали в выдачу</p>${body}`);
}

function emptyQueriesCard(queries) {
  const count = queries.length ? `<span class="a-count">${queries.length}</span>` : '';
  const body = queries.length
    ? `<ul class="a-list a-list--tall">${queries.map((q) => `
        <li class="a-row a-row--query">
          <div class="a-row__main">
            <span class="a-row__name">${escapeHtml(q.query)}</span>
            <span class="a-row__date">${formatDateTime(q.at)}</span>
          </div>
          <button class="a-del" type="button" data-delete="${q.id}" aria-label="Удалить запись">✕</button>
        </li>`).join('')}</ul>`
    : emptyNote('Запросов без результатов нет');
  return card('Запросы без результатов', body, count);
}

// ===== Загрузка данных =====

async function load() {
  renderLoading();
  try {
    const [stats, memes, queries] = await Promise.all([
      adminApi.getStats(period),
      adminApi.getMemeStats(),
      adminApi.getEmptyQueries(),
    ]);
    adminBox.innerHTML = `
      <div class="admin__col" id="left">${renderLeft(stats)}</div>
      <div class="admin__col" id="right">
        ${topMemesCard(memes.top)}
        ${deadMemesCard(memes.dead)}
        <div id="queries">${emptyQueriesCard(queries)}</div>
      </div>`;
  } catch (e) {
    if (e.message === 'UNAUTHORIZED' || e.message === 'FORBIDDEN') renderForbidden();
    else renderError();
  }
}

// Переключение периода — перерисовываем только левую часть
async function changePeriod(next) {
  if (next === period) return;
  period = next;
  const left = document.getElementById('left');
  left.classList.add('is-updating');
  try {
    left.innerHTML = renderLeft(await adminApi.getStats(period));
  } catch (e) {
    renderError();
    return;
  }
  left.classList.remove('is-updating');
}

async function deleteQuery(id, button) {
  button.disabled = true;
  await adminApi.deleteEmptyQuery(id);
  document.getElementById('queries').innerHTML = emptyQueriesCard(await adminApi.getEmptyQueries());
  showToast('Запись удалена');
}

adminBox.addEventListener('click', (event) => {
  const periodBtn = event.target.closest('[data-period]');
  if (periodBtn) return changePeriod(periodBtn.dataset.period);
  const del = event.target.closest('[data-delete]');
  if (del) deleteQuery(del.dataset.delete, del);
});

// Подсказка над столбиком графика
adminBox.addEventListener('mouseover', (event) => {
  const bar = event.target.closest('.a-bar');
  const chart = event.target.closest('.a-chart');
  if (!chart) return;
  const tip = chart.querySelector('.a-tip');
  chart.querySelectorAll('.a-bar').forEach((b) => b.classList.toggle('is-hover', b === bar));
  if (!bar) return (tip.hidden = true);
  const box = bar.querySelector('path').getBoundingClientRect();
  const base = chart.getBoundingClientRect();
  tip.textContent = bar.dataset.tip;
  tip.hidden = false;
  tip.style.left = `${box.left - base.left + box.width / 2}px`;
  tip.style.top = `${box.top - base.top - 8}px`;
});
adminBox.addEventListener('mouseout', (event) => {
  const chart = event.target.closest('.a-chart');
  if (!chart || chart.contains(event.relatedTarget)) return; // ушли за пределы графика
  chart.querySelector('.a-tip').hidden = true;
  chart.querySelectorAll('.a-bar.is-hover').forEach((b) => b.classList.remove('is-hover'));
});

// ===== Запуск =====
(async () => {
  const user = await api.getCurrentUser();
  if (user) {
    document.getElementById('admin-user').innerHTML = `
      <span class="admin-user">${avatarHtml(user)}<span>${escapeHtml(user.nickname)}</span></span>`;
  }
  load();
})();
