/*
 * Учётная запись: кнопка в правом верхнем углу, окно входа/регистрации,
 * окно настроек профиля.
 */

const authModal = document.getElementById('auth-modal');
const profileModal = document.getElementById('profile-modal');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const profileForm = document.getElementById('profile-form');

// ===== Правый верхний угол =====
function renderProfile() {
  const box = document.getElementById('profile');
  if (!state.user) {
    box.innerHTML = '<button class="btn" type="button" data-open-auth>Войти</button>';
    return;
  }
  box.innerHTML = `
    <button class="profile-btn" type="button" id="open-profile">
      ${avatarHtml(state.user)}
      <span class="profile-btn__name">${escapeHtml(state.user.nickname)}</span>
    </button>`;
  document.getElementById('open-profile').addEventListener('click', openProfile);
}

// Любая кнопка с data-open-auth открывает окно входа
document.addEventListener('click', (event) => {
  if (event.target.closest('[data-open-auth]')) {
    switchTab('login');
    closeSidebar();
    openModal(authModal);
  }
});

// ===== Вход / регистрация =====

function switchTab(tab) {
  authModal.querySelectorAll('.tabs__btn').forEach((btn) =>
    btn.classList.toggle('tabs__btn--active', btn.dataset.tab === tab)
  );
  loginForm.hidden = tab !== 'login';
  registerForm.hidden = tab !== 'register';
  setFormError(loginForm, '');
  setFormError(registerForm, '');
  const firstInput = (tab === 'login' ? loginForm : registerForm).querySelector('input');
  if (!authModal.hidden) firstInput.focus();
}

authModal.addEventListener('click', (event) => {
  const tabBtn = event.target.closest('[data-tab]');
  if (tabBtn) switchTab(tabBtn.dataset.tab);
});

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const loginValue = loginForm.login.value.trim();
  const password = loginForm.password.value;
  if (!loginValue || !password) return setFormError(loginForm, 'Введите логин и пароль');

  setFormBusy(loginForm, true);
  try {
    const user = await api.login(loginValue, password);
    await onSignedIn(user);
    loginForm.reset();
  } catch (e) {
    setFormError(loginForm, e.message);
  } finally {
    setFormBusy(loginForm, false);
  }
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const f = registerForm;
  if (f.password.value !== f.password2.value) return setFormError(f, 'Пароли не совпадают');

  setFormBusy(f, true);
  try {
    const user = await api.register({
      login: f.login.value,
      nickname: f.nickname.value,
      password: f.password.value,
    });
    await onSignedIn(user);
    f.reset();
  } catch (e) {
    setFormError(f, e.message);
  } finally {
    setFormBusy(f, false);
  }
});

// После входа: обновляем интерфейс, а начатый гостем чат сохраняем в историю
async function onSignedIn(user) {
  state.user = user;
  if (state.chat && state.chat.messages.length) {
    await persistChat(state.chat);
  }
  closeModal(authModal);
  renderProfile();
  renderSidebar();
  showToast(`Привет, ${user.nickname}!`);
}

// ===== Профиль =====
let pendingAvatar = null; // фото, выбранное в окне, но ещё не сохранённое

function openProfile() {
  pendingAvatar = state.user.avatar;
  profileForm.nickname.value = state.user.nickname;
  document.getElementById('profile-login').textContent = state.user.login;
  document.getElementById('admin-link').hidden = state.user.role !== 'admin';
  renderProfileAvatar();
  setFormError(profileForm, '');
  openModal(profileModal);
}

function renderProfileAvatar() {
  const preview = { ...state.user, nickname: profileForm.nickname.value || state.user.nickname, avatar: pendingAvatar };
  document.getElementById('profile-avatar').innerHTML = avatarHtml(preview, 'large');
  document.getElementById('avatar-remove').hidden = !pendingAvatar;
}

profileForm.nickname.addEventListener('input', renderProfileAvatar);

// Выбор фото: уменьшаем до 160×160, чтобы не занимать много места
document.getElementById('avatar-input').addEventListener('change', (event) => {
  const file = event.target.files[0];
  event.target.value = ''; // чтобы можно было выбрать тот же файл ещё раз
  if (!file) return;
  if (!file.type.startsWith('image/')) return setFormError(profileForm, 'Выберите картинку');

  const img = new Image();
  img.onload = () => {
    const size = 160;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const side = Math.min(img.width, img.height); // обрезаем по центру в квадрат
    canvas.getContext('2d').drawImage(
      img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size
    );
    pendingAvatar = canvas.toDataURL('image/jpeg', 0.85);
    URL.revokeObjectURL(img.src);
    setFormError(profileForm, '');
    renderProfileAvatar();
  };
  img.onerror = () => setFormError(profileForm, 'Не получилось открыть картинку');
  img.src = URL.createObjectURL(file);
});

document.getElementById('avatar-remove').addEventListener('click', () => {
  pendingAvatar = null;
  renderProfileAvatar();
});

profileForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  setFormBusy(profileForm, true);
  try {
    state.user = await api.updateProfile({ nickname: profileForm.nickname.value, avatar: pendingAvatar });
    renderProfile();
    closeModal(profileModal);
    showToast('Профиль сохранён');
  } catch (e) {
    setFormError(profileForm, e.message);
  } finally {
    setFormBusy(profileForm, false);
  }
});

// Выход: теряем авторизацию, история недоступна, интерфейс — как у гостя
document.getElementById('logout').addEventListener('click', async () => {
  await api.logout();
  state.user = null;
  state.chat = null;
  closeModal(profileModal);
  renderProfile();
  renderSidebar();
  renderChat();
  showToast('Вы вышли из аккаунта');
});
