/*
 * Общие маленькие функции для всего сайта.
 */

// Экранируем текст пользователя, чтобы <script> в сообщении не стал кодом
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Склонение: plural(5, 'мем', 'мема', 'мемов') → 'мемов'
function plural(n, one, few, many) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

// Аватар: фото, а если его нет — первая буква никнейма в жёлтом кружке
function avatarHtml(user, size = 'small') {
  const cls = `avatar avatar--${size}`;
  if (user.avatar) {
    return `<img class="${cls}" src="${user.avatar}" alt="">`;
  }
  const letter = (user.nickname || user.login || '?').trim().charAt(0).toUpperCase();
  return `<span class="${cls}" aria-hidden="true">${escapeHtml(letter)}</span>`;
}

// Всплывающее уведомление внизу экрана
function showToast(text) {
  document.querySelector('.toast')?.remove();
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = text;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2500);
}

// ===== Модальные окна =====
// Открытое окно закрывается крестиком, кликом по фону или клавишей Esc.

function openModal(modal) {
  modal.hidden = false;
  document.body.classList.add('no-scroll');
  // Ставим курсор в первое видимое поле
  const input = modal.querySelector('form:not([hidden]) input:not([type=file])');
  if (input) input.focus();
}

function closeModal(modal) {
  modal.hidden = true;
  document.body.classList.remove('no-scroll');
}

document.addEventListener('click', (event) => {
  const closer = event.target.closest('[data-close]');
  if (closer) closeModal(closer.closest('.modal'));
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  document.querySelectorAll('.modal:not([hidden])').forEach(closeModal);
});

// Показать / спрятать ошибку в форме
function setFormError(form, text) {
  const error = form.querySelector('.form-error');
  error.textContent = text || '';
  error.hidden = !text;
}

// Блокируем кнопку, пока идёт запрос (чтобы не отправили дважды)
function setFormBusy(form, busy) {
  const button = form.querySelector('button[type=submit]');
  button.disabled = busy;
}
