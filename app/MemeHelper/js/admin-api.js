/* Реальные события сервера, без вымышленных демо-данных. */
const adminApi = {
  getStats: (period) => api.request('/api/admin/stats?period=' + encodeURIComponent(period)),
  getMemeStats: () => api.request('/api/admin/memes'),
  getEmptyQueries: () => api.request('/api/admin/empty-queries'),
  deleteEmptyQuery: (id) => api.request('/api/admin/empty-queries/' + encodeURIComponent(id), 'DELETE'),
  addMeme: (meme) => api.request('/api/admin/memes', 'POST', meme),
};
