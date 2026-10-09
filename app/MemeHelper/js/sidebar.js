/*
 * Левая область: история чатов.
 * Гость — только кнопка «Новый чат» и предложение войти.
 * Вошедший — список прошлых чатов.
 */

const sidebar = document.getElementById('sidebar');
const sidebarBody = document.getElementById('sidebar-body');
const sidebarOverlay = document.getElementById('sidebar-overlay');

async function renderSidebar() {
  // Гость: истории нет, предлагаем войти (состояние Unauthorized)
  if (!state.user) {
    sidebarBody.innerHTML = `
      <div class="sidebar-note">
        <p class="sidebar-note__title">История чатов</p>
        <p>Войдите, чтобы ваши чаты сохранялись и к ним можно было вернуться.</p>
        <button class="btn btn--small" type="button" data-open-auth>Войти</button>
      </div>`;
    return;
  }

  const chats = await api.listChats();
  if (!chats.length) {
    sidebarBody.innerHTML = '<p class="sidebar-empty">Здесь появятся ваши чаты</p>';
    return;
  }

  sidebarBody.innerHTML = `
    <p class="sidebar__label">История</p>
    <ul class="chat-list">
      ${chats
        .map(
          (chat) => `
        <li class="chat-list__item${chat.id === state.chat?.id ? ' chat-list__item--active' : ''}">
          <button class="chat-list__open" type="button" data-chat="${chat.id}" title="${escapeHtml(chat.title)}">
            ${escapeHtml(chat.title || 'Без названия')}
          </button>
          <button class="chat-list__delete" type="button" data-delete="${chat.id}" aria-label="Удалить чат">✕</button>
        </li>`
        )
        .join('')}
    </ul>`;
}

// Выбор чата: текущий диалог заменяется выбранным, сообщения грузятся из истории
async function openChat(id) {
  if (state.loading) return;
  state.chat = await api.getChat(id);
  renderChat();
  renderSidebar();
  closeSidebar();
}

async function removeChat(id) {
  await api.deleteChat(id);
  if (state.chat?.id === id) {
    state.chat = null;
    renderChat();
  }
  renderSidebar();
}

function newChat() {
  if (state.loading) return;
  state.chat = null;
  renderChat();
  renderSidebar();
  closeSidebar();
  input.focus();
}

sidebarBody.addEventListener('click', (event) => {
  const del = event.target.closest('[data-delete]');
  if (del) return removeChat(del.dataset.delete);
  const open = event.target.closest('[data-chat]');
  if (open) openChat(open.dataset.chat);
});

document.getElementById('new-chat').addEventListener('click', newChat);

// ===== Мобильная версия: сайдбар выезжает слева =====
function openSidebar() {
  sidebar.classList.add('sidebar--open');
  sidebarOverlay.hidden = false;
}
function closeSidebar() {
  sidebar.classList.remove('sidebar--open');
  sidebarOverlay.hidden = true;
}
document.getElementById('sidebar-open').addEventListener('click', openSidebar);
document.getElementById('sidebar-close').addEventListener('click', closeSidebar);
sidebarOverlay.addEventListener('click', closeSidebar);
