package main

import (
	"io"
	"net/http"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

// blockingReader 阻塞在 Read 上,直到被 Close;用于模拟上游卡死不返回。
type blockingReader struct {
	closed chan struct{}
	once   sync.Once
}

func newBlockingReader() *blockingReader {
	return &blockingReader{closed: make(chan struct{})}
}

func (b *blockingReader) Read(p []byte) (int, error) {
	<-b.closed
	return 0, io.EOF
}

func (b *blockingReader) Close() error {
	b.once.Do(func() { close(b.closed) })
	return nil
}

// TestReadAllWithTimeoutTimeout 验证非流式整体超时:数据源卡死时返回超时错误。
func TestReadAllWithTimeoutTimeout(t *testing.T) {
	start := time.Now()
	data, err := readAllWithTimeout(newBlockingReader(), 1<<20, 100*time.Millisecond)
	require.Error(t, err)
	require.Contains(t, err.Error(), "timeout")
	require.Nil(t, data)
	require.Less(t, time.Since(start), 5*time.Second, "超时后应立即返回")
}

// TestReadAllWithTimeoutPass 验证非流式整体超时:正常数据源原样读取。
func TestReadAllWithTimeoutPass(t *testing.T) {
	data, err := readAllWithTimeout(strings.NewReader("hello"), 1<<20, time.Second)
	require.NoError(t, err)
	require.Equal(t, "hello", string(data))
}

// TestStreamIdleReaderTimeout 验证流式空闲超时:两次 Read 之间卡死时返回错误。
func TestStreamIdleReaderTimeout(t *testing.T) {
	br := newBlockingReader()
	r := newStreamIdleReader(br, br, 100*time.Millisecond)
	buf := make([]byte, 32)
	start := time.Now()
	_, err := r.Read(buf)
	require.Error(t, err)
	require.Contains(t, err.Error(), "idle timeout")
	require.Less(t, time.Since(start), 5*time.Second)
}

// TestStreamIdleReaderPass 验证流式空闲超时:正常数据可全部读出。
func TestStreamIdleReaderPass(t *testing.T) {
	r := newStreamIdleReader(strings.NewReader("data"), io.NopCloser(strings.NewReader("")), time.Second)
	buf := make([]byte, 32)
	n, err := r.Read(buf)
	require.NoError(t, err)
	require.Equal(t, "data", string(buf[:n]))
	n, err = r.Read(buf)
	require.Equal(t, io.EOF, err)
	require.Equal(t, 0, n)
}

// TestCopyBodyWithTimeout 验证流式透传阶段空闲超时:卡死时返回超时错误。
func TestCopyBodyWithTimeout(t *testing.T) {
	br := newBlockingReader()
	var dst strings.Builder
	start := time.Now()
	err := copyBodyWithTimeout(&dst, br, br, 100*time.Millisecond)
	require.Error(t, err)
	require.Contains(t, err.Error(), "idle timeout")
	require.Less(t, time.Since(start), 5*time.Second)
}

// TestGatewayStreamIdleTimeoutSwitch 集成验证:第一个上游流中途卡死,
// 空闲超时后自动切换,由第二个上游成功返回。
func TestGatewayStreamIdleTimeoutSwitch(t *testing.T) {
	stallCfg, _, stallCalls := fakeUpstream(t, "stall", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"stall..."}}]}`)))
		w.(http.Flusher).Flush()
		<-r.Context().Done() // 卡死不再返回
	})
	stallCfg.Weight = 100 // 确保先选中它

	okCfg, _, okCalls := fakeUpstream(t, "ok", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(
			`{"choices":[{"delta":{"reasoning_content":"real thinking"}}]}`,
			`{"choices":[{"delta":{"content":"real answer"}}]}`,
			`[DONE]`,
		)))
	})
	okCfg.Weight = 1

	cfg := &Config{
		Upstreams:         []UpstreamConfig{stallCfg, okCfg},
		RetryTimes:        3,
		MaxBodySize:       1 << 20,
		Circuit:           CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL:    60,
		StreamIdleTimeout: 1, // 1 秒空闲超时
	}
	gw := NewGateway(cfg)

	body := `{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"stream":true,"reasoning_effort":"high"}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "real thinking", "应切换到第二个上游并收到思考内容")
	require.Contains(t, respBody, "real answer")
	require.GreaterOrEqual(t, stallCalls.Load(), int32(1), "卡死上游应被尝试过")
	require.GreaterOrEqual(t, okCalls.Load(), int32(1), "应切换到正常上游")
}
