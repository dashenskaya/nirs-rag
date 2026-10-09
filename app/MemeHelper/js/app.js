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
  state.user = await api.getCurrentUser();
  renderProfile();
  renderSidebar();
  renderChat();
  input.focus();
})();
