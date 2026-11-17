/* Все данные приходят с сервера. Открывайте сайт через start.cmd. */
const api = (() => {
  async function request(path, method = 'GET', body) {
    if (location.protocol === 'file:') throw new Error('Запустите start.cmd и откройте http://127.0.0.1:8000');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch(path, {
        method, credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'MemeHelper' },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || 'Не удалось выполнить запрос');
      return value;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Сервер не ответил за 2 минуты. Попробуйте ещё раз.');
      if (error instanceof TypeError) throw new Error('Нет связи с сервером. Проверьте, что start.cmd запущен.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  return {
    request,
    health: () => request('/api/health'),
    getCurrentUser: () => request('/api/me'),
    login: (login, password) => request('/api/auth/login', 'POST', { login, password }),
    register: (data) => request('/api/auth/register', 'POST', data),
    logout: () => request('/api/auth/logout', 'POST', {}),
    updateProfile: (data) => request('/api/me', 'PATCH', data),
    listChats: () => request('/api/chats'),
    getChat: (id) => request('/api/chats/' + encodeURIComponent(id)),
    saveChat: (chat) => request('/api/chats/' + encodeURIComponent(chat.id), 'PUT', chat),
    deleteChat: (id) => request('/api/chats/' + encodeURIComponent(id), 'DELETE'),
    searchMemes: (query) => request('/api/search', 'POST', { query }),
  };
})();
