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

  // Читает Server-Sent Events и передаёт готовые части ответа в чат.
  async function streamSearchMemes(query, onEvent = () => {}) {
    if (location.protocol === 'file:') throw new Error('Запустите start.cmd и откройте http://127.0.0.1:8000');

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 180000);
    let reader;

    try {
      const response = await fetch('/api/search/stream', {
        method: 'POST',
        credentials: 'same-origin',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'MemeHelper',
        },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.error || 'Не удалось выполнить поиск мемов');
      }
      if (!response.body) throw new Error('Браузер не поддерживает потоковую передачу ответа');

      reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let finalResult = null;

      const processFrame = (frame) => {
        let eventName = 'message';
        const dataLines = [];

        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
        }

        if (!dataLines.length) return;
        let payload;
        try {
          payload = JSON.parse(dataLines.join('\n'));
        } catch {
          return;
        }

        if (eventName === 'error') {
          throw new Error(payload.error || 'Ошибка потокового поиска');
        }
        if (eventName === 'done') {
          finalResult = payload;
          return;
        }
        onEvent(eventName, payload);
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
        let frameEnd;
        while ((frameEnd = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, frameEnd);
          buffer = buffer.slice(frameEnd + 2);
          processFrame(frame);
        }
      }

      buffer += decoder.decode();
      if (buffer.trim()) processFrame(buffer);
      if (!finalResult) throw new Error('Поток завершился без итогового ответа сервера');
      return finalResult;

    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Ожидание ответа превысило 3 минуты. Попробуйте ещё раз.');
      if (error instanceof TypeError) throw new Error('Нет связи с сервером. Проверьте, что start.cmd запущен.');
      throw error;
    } finally {
      clearTimeout(timer);
      if (reader) {
        try { reader.releaseLock(); } catch { /* поток уже закрыт */ }
      }
    }
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
    // Совместимость со старым chat.js: также используем потоковый endpoint.
    // Без callback ответ просто будет собран целиком до возврата вызывающему коду.
    searchMemes: (query) => streamSearchMemes(query),
    streamSearchMemes,
  };
})();
