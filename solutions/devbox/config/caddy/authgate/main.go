// =============================================================================
// auth-gate —— devbox 统一会话鉴权微服务（R4 方案落地）
// 文档编号：RT-002 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao
// 职责：登录页 + HMAC 签名 Cookie 会话（默认 7 天）+ forward_auth /verify 校验
// 环境变量：AUTH_USER / AUTH_PASSWORD / SESSION_TTL_HOURS / COOKIE_SECRET / LISTEN_ADDR
// =============================================================================

package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const cookieName = "devbox_auth"

var (
	authUser  string
	authPass  string
	cookieSec []byte
	ttlHours  int
)

func sign(payload string) string {
	mac := hmac.New(sha256.New, cookieSec)
	mac.Write([]byte(payload))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func makeCookie(user string) *http.Cookie {
	exp := time.Now().Add(time.Duration(ttlHours) * time.Hour).Unix()
	payload := fmt.Sprintf("%s|%d", user, exp)
	return &http.Cookie{
		Name:     cookieName,
		Value:    payload + "." + sign(payload),
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   ttlHours * 3600,
	}
}

func valid(r *http.Request) (string, bool) {
	c, err := r.Cookie(cookieName)
	if err != nil || c.Value == "" {
		return "", false
	}
	parts := strings.SplitN(c.Value, ".", 2)
	if len(parts) != 2 {
		return "", false
	}
	payload, sig := parts[0], parts[1]
	if subtle.ConstantTimeCompare([]byte(sig), []byte(sign(payload))) != 1 {
		return "", false
	}
	kv := strings.SplitN(payload, "|", 2)
	if len(kv) != 2 {
		return "", false
	}
	exp, err := strconv.ParseInt(kv[1], 10, 64)
	if err != nil || time.Now().Unix() > exp {
		return "", false
	}
	return kv[0], true
}

func safeNext(next string) string {
	if next == "" || !strings.HasPrefix(next, "/") || strings.HasPrefix(next, "//") {
		return "/"
	}
	return next
}

func renderLogin(w http.ResponseWriter, next, msg string) {
	msgHTML := ""
	if msg != "" {
		msgHTML = `<p class="err">` + msg + `</p>`
	}
	fmt.Fprintf(w, `<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DevBox 登录</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;
justify-content:center;align-items:center;height:100vh;margin:0}
.card{background:#1e293b;padding:2rem 2.5rem;border-radius:12px;min-width:300px}
h1{font-size:1.2rem;margin-top:0}input{width:100%%;box-sizing:border-box;padding:.6rem;margin:.4rem 0;
border-radius:6px;border:1px solid #334155;background:#0f172a;color:#e2e8f0}
button{width:100%%;padding:.6rem;margin-top:.8rem;border:0;border-radius:6px;background:#3b82f6;color:#fff}
.err{color:#f87171;font-size:.85rem}.hint{color:#94a3b8;font-size:.75rem;margin-top:1rem}</style></head>
<body><div class="card"><h1>ZeekDevAI DevBox</h1>%s
<form method="post" action="/login">
<input type="hidden" name="next" value="%s">
<input name="username" placeholder="用户名" required autofocus>
<input name="password" type="password" placeholder="密码" required>
<button type="submit">登录</button></form>
<p class="hint">登录一次，导航 / 终端 / 文件共享共享会话（默认 %d 小时）</p></div></body></html>`,
		msgHTML, next, ttlHours)
}

func loginHandler(w http.ResponseWriter, r *http.Request) {
	next := safeNext(r.URL.Query().Get("next"))
	if r.Method == http.MethodPost {
		if err := r.ParseForm(); err == nil {
			u := r.FormValue("username")
			p := r.FormValue("password")
			uOK := subtle.ConstantTimeCompare([]byte(u), []byte(authUser)) == 1
			pOK := subtle.ConstantTimeCompare([]byte(p), []byte(authPass)) == 1
			if uOK && pOK {
				http.SetCookie(w, makeCookie(u))
				http.Redirect(w, r, safeNext(r.FormValue("next")), http.StatusFound)
				return
			}
			renderLogin(w, next, "用户名或密码错误")
			return
		}
	}
	renderLogin(w, next, "")
}

func logoutHandler(w http.ResponseWriter, r *http.Request) {
	http.SetCookie(w, &http.Cookie{Name: cookieName, Value: "", Path: "/", MaxAge: -1})
	http.Redirect(w, r, "/login", http.StatusFound)
}

func verifyHandler(w http.ResponseWriter, r *http.Request) {
	if _, ok := valid(r); ok {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	next := r.Header.Get("X-Forwarded-Uri")
	http.Redirect(w, r, "/login?next="+url.QueryEscape(safeNext(next)), http.StatusFound)
}

func healthzHandler(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte("ok"))
}

func main() {
	authUser = os.Getenv("AUTH_USER")
	authPass = os.Getenv("AUTH_PASSWORD")
	if authUser == "" || authPass == "" {
		panic("AUTH_USER / AUTH_PASSWORD 必须设置")
	}
	sec := os.Getenv("COOKIE_SECRET")
	if sec == "" {
		panic("COOKIE_SECRET 必须设置")
	}
	cookieSec = []byte(sec)
	ttlHours = 168
	if v := os.Getenv("SESSION_TTL_HOURS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			ttlHours = n
		}
	}
	addr := os.Getenv("LISTEN_ADDR")
	if addr == "" {
		addr = "127.0.0.1:9090"
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/login", loginHandler)
	mux.HandleFunc("/logout", logoutHandler)
	mux.HandleFunc("/verify", verifyHandler)
	mux.HandleFunc("/healthz", healthzHandler)
	fmt.Printf("[auth-gate] listening on %s (session %dh)\n", addr, ttlHours)
	if err := http.ListenAndServe(addr, mux); err != nil {
		panic(err)
	}
}
