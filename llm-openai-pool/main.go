package main

import (
	"context"
	"flag"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	configPath := flag.String("config", "config.json", "配置文件路径")
	flag.Parse()

	if !ensureConfig(*configPath) {
		os.Exit(1)
	}

	cfg, err := LoadConfig(*configPath)
	if err != nil {
		log.Fatalf("加载配置失败: %v", err)
	}

	gw := NewGateway(cfg)

	mux := http.NewServeMux()
	mux.HandleFunc("/v1/", gw.handleRelay)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	server := &http.Server{
		Addr:              cfg.Listen,
		Handler:           mux,
		ReadHeaderTimeout: 30 * time.Second,
	}

	go func() {
		log.Printf("openai-pool 已启动,监听 %s,上游 %d 个: %v", cfg.Listen, len(cfg.Upstreams), gw.pool.Names())
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("监听失败: %v", err)
		}
	}()

	// 每 30 秒打印一次上游状态,便于观察熔断与占用
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for range ticker.C {
			gw.pool.LogState()
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
	log.Println("正在关闭...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	server.Shutdown(ctx)
	log.Println("已退出")
}

// ensureConfig 检查配置文件是否存在;不存在时尝试从同目录的
// config.json.example 复制一份并提示用户填写,返回 false 表示应退出。
func ensureConfig(configPath string) bool {
	_, err := os.Stat(configPath)
	if err == nil {
		return true
	}
	if !os.IsNotExist(err) {
		log.Printf("检查配置 %s 失败: %v", configPath, err)
		return false
	}

	examplePath := configPath + ".example"
	src, err := os.Open(examplePath)
	if err != nil {
		log.Printf("配置 %s 不存在,且示例 %s 也无法读取: %v", configPath, examplePath, err)
		return false
	}
	defer src.Close()

	dst, err := os.Create(configPath)
	if err != nil {
		log.Printf("配置 %s 不存在,创建 %s 失败: %v", configPath, configPath, err)
		return false
	}
	defer dst.Close()

	if _, err := io.Copy(dst, src); err != nil {
		log.Printf("复制示例配置失败: %v", err)
		return false
	}

	log.Printf("配置 %s 不存在,已从 %s 创建,请编辑 %s 填写真实的上游地址与 API Key 后重新启动", configPath, examplePath, configPath)
	return false
}
