/*
 * Запуск приложения. Здесь хранится общее состояние,
 * которое читают chat.js, sidebar.js и auth.js.
 */
const state = {
  user: null,     // кто вошёл (null — гость)
  chat: null,     // открытый чат (null — новый, пустой)
  loading: false, // ждём ответ от «ИИ»
};

(async () => {
  try {
    const [user, health] = await Promise.all([api.getCurrentUser(), api.health()]);
    state.user = user;
    document.getElementById('search-mode').hidden = health.searchMode !== 'demo';
    renderProfile();
    await renderSidebar();
    renderChat();
    input.focus();
  } catch (error) {
    messagesBox.textContent = error.message;
    input.disabled = sendButton.disabled = true;
  }
})();
