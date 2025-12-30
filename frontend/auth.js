function login() {
  const u = document.getElementById("username").value.trim();
  const p = document.getElementById("password").value.trim();

  if (!u || !p) {
    alert("نام کاربری و رمز عبور را وارد کنید");
    return;
  }

  // لاگین فیک
  localStorage.setItem("logged_in", "true");
  localStorage.setItem("user", u);

  window.location.href = "/";
}

function logout() {
  localStorage.clear();
  window.location.href = "/login";
}

function requireAuth() {
  if (!localStorage.getItem("logged_in")) {
    window.location.href = "/login";
  }
}
