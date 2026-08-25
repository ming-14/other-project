package main

import (
	"crypto/subtle"
	"net/http"
	"strings"
)

// checkAuth 校验本地出口鉴权:配置了 LocalKeys 时,请求必须携带
// Authorization: Bearer <key> 且 key 在列表中;未配置 LocalKeys 则放行。
func checkAuth(r *http.Request, cfg *Config) bool {
	if len(cfg.LocalKeys) == 0 {
		return true
	}
	auth := r.Header.Get("Authorization")
	const prefix = "Bearer "
	if !strings.HasPrefix(auth, prefix) {
		return false
	}
	key := strings.TrimSpace(strings.TrimPrefix(auth, prefix))
	for _, k := range cfg.LocalKeys {
		if subtle.ConstantTimeCompare([]byte(key), []byte(k)) == 1 {
			return true
		}
	}
	return false
}

func writeUnauthorized(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	w.Write([]byte(`{"error":{"message":"invalid local api key","type":"invalid_request_error","code":"invalid_api_key"}}`))
}
