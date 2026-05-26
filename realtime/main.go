/*
Iosef Finance – Realtime WebSocket Microservice (Go + Redis)
=============================================================
Architecture:
  - Hub          → manages all active WebSocket connections (goroutine-safe)
  - RedisFetcher → polls Redis "scan:data" every 3s in its own goroutine
  - Broadcaster  → fans out full market scan (indicators, prices, movers) to clients
  - Each client  → gets its own read/write goroutines (non-blocking)

Endpoints:
  - ws://localhost:8080/ws/market
  - http://localhost:8080/health
*/

package main

import (
	"context"
	"encoding/json"
	"log"
	"math"
	"net/http"
	"os"
	"sort"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
)

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

var (
	listenAddr     = envOrDefault("WS_LISTEN", ":8080") // Updated to 8080 as requested
	redisAddr      = envOrDefault("REDIS_HOST", "localhost") + ":" + envOrDefault("REDIS_PORT", "6379")
	fetchInterval  = 3 * time.Second
	topMoversCount = 5
	markets        = []string{"nasdaq100", "sp500", "europe"}
)

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

var ctx = context.Background()
var rdb *redis.Client

func initRedis() {
	rdb = redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: "", 
		DB:       0,  
	})
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("[redis] Could not connect to Redis at %s: %v", redisAddr, err)
	}
	log.Printf("[redis] Connected successfully to %s", redisAddr)
}

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

type TickerData struct {
	Ticker            string  `json:"ticker"`
	Price             float64 `json:"price"`
	ChangePct         float64 `json:"change_pct"`
	RSI               float64 `json:"rsi"`
	SMA20             float64 `json:"sma20"`
	SMA50             float64 `json:"sma50"`
	SMA200            float64 `json:"sma200"`
	Momentum1M        float64 `json:"momentum_1m"`
	RelativeVolume    float64 `json:"relative_volume"`
	CompositeScore    int     `json:"composite_score"`
	MAPreakoutSignal  bool    `json:"ma_breakout_signal"`
	Sector            *string `json:"sector"`
	Industry          *string `json:"industry"`
}

type ScanResponse struct {
	Timestamp float64       `json:"timestamp"`
	Data      []TickerData  `json:"data"`
	Alerts    []interface{} `json:"alerts"`
}

// The payload we broadcast to WebSocket clients containing full data
type MarketSnapshot struct {
	Timestamp  float64       `json:"timestamp"`
	Market     string        `json:"market"`
	Tickers    []TickerData  `json:"tickers"`
	TopGainers []TickerData  `json:"top_gainers"`
	TopLosers  []TickerData  `json:"top_losers"`
	Alerts     []interface{} `json:"alerts"`
	FetchedAt  string        `json:"fetched_at"`
}

// ---------------------------------------------------------------------------
// Hub – manages WebSocket clients (goroutine-safe)
// ---------------------------------------------------------------------------

type Client struct {
	conn *websocket.Conn
	send chan []byte
}

type Hub struct {
	mu         sync.RWMutex
	clients    map[*Client]bool
	register   chan *Client
	unregister chan *Client
	broadcast  chan []byte
}

func newHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		register:   make(chan *Client, 64),
		unregister: make(chan *Client, 64),
		broadcast:  make(chan []byte, 16),
	}
}

func (h *Hub) run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			count := len(h.clients)
			h.mu.Unlock()
			log.Printf("[hub] Client connected. Total: %d", count)

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			count := len(h.clients)
			h.mu.Unlock()
			log.Printf("[hub] Client disconnected. Total: %d", count)

		case msg := <-h.broadcast:
			h.mu.RLock()
			for client := range h.clients {
				select {
				case client.send <- msg:
				default:
					go func(c *Client) {
						h.unregister <- c
						c.conn.Close()
					}(client)
				}
			}
			h.mu.RUnlock()
		}
	}
}

func (c *Client) writePump() {
	defer c.conn.Close()
	for msg := range c.send {
		if err := c.conn.WriteMessage(websocket.TextMessage, msg); err != nil {
			return
		}
	}
}

func (c *Client) readPump(h *Hub) {
	defer func() {
		h.unregister <- c
		c.conn.Close()
	}()
	c.conn.SetReadLimit(512)
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})
	for {
		if _, _, err := c.conn.ReadMessage(); err != nil {
			break
		}
	}
}

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 4096,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

func wsHandler(hub *Hub, w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[ws] Upgrade error: %v", err)
		return
	}
	client := &Client{conn: conn, send: make(chan []byte, 32)}
	hub.register <- client

	go client.writePump()
	go client.readPump(hub)
}

// ---------------------------------------------------------------------------
// Data fetcher – reads from Redis directly
// ---------------------------------------------------------------------------

func fetchFromRedis(market string) (*ScanResponse, error) {
	val, err := rdb.Get(ctx, "scan:data:"+market).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, nil
		}
		return nil, err
	}

	var scan ScanResponse
	if err := json.Unmarshal([]byte(val), &scan); err != nil {
		return nil, err
	}
	return &scan, nil
}

func buildSnapshot(scan *ScanResponse, market string) *MarketSnapshot {
	if scan == nil || len(scan.Data) == 0 {
		return nil
	}

	// Sort for gainers (desc) and losers (asc)
	sorted := make([]TickerData, len(scan.Data))
	copy(sorted, scan.Data)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].ChangePct > sorted[j].ChangePct
	})

	n := int(math.Min(float64(topMoversCount), float64(len(sorted))))

	gainers := make([]TickerData, n)
	losers := make([]TickerData, n)

	for i := 0; i < n; i++ {
		gainers[i] = sorted[i]
		losers[i] = sorted[len(sorted)-1-i]
	}

	return &MarketSnapshot{
		Timestamp:  scan.Timestamp,
		Market:     market,
		Tickers:    scan.Data, // Include full data
		TopGainers: gainers,
		TopLosers:  losers,
		Alerts:     scan.Alerts,
		FetchedAt:  time.Now().UTC().Format(time.RFC3339),
	}
}

func dataFetcher(hub *Hub) {
	log.Printf("[fetcher] Reading from Redis for markets %v every %v", markets, fetchInterval)
	for {
		for _, market := range markets {
			scan, err := fetchFromRedis(market)
			if err != nil {
				log.Printf("[fetcher] Error reading %s from Redis: %v", market, err)
				continue
			}

			snapshot := buildSnapshot(scan, market)
			if snapshot != nil {
				if payload, err := json.Marshal(snapshot); err == nil {
					hub.broadcast <- payload
				}
			}
		}

		time.Sleep(fetchInterval)
	}
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

func healthHandler(hub *Hub) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hub.mu.RLock()
		count := len(hub.clients)
		hub.mu.RUnlock()

		redisStatus := "ok"
		if err := rdb.Ping(ctx).Err(); err != nil {
			redisStatus = "error"
		}

		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":            "ok",
			"redis_status":      redisStatus,
			"connected_clients": count,
			"uptime":            time.Since(startTime).String(),
		})
	}
}

var startTime = time.Now()

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

func main() {
	initRedis()
	hub := newHub()
	go hub.run()
	go dataFetcher(hub)

	http.HandleFunc("/ws/market", func(w http.ResponseWriter, r *http.Request) {
		wsHandler(hub, w, r)
	})
	http.HandleFunc("/health", healthHandler(hub))

	log.Printf("=== Iosef Realtime WS Server (Redis Powered) ===")
	log.Printf("Listening on %s", listenAddr)
	log.Printf("WebSocket endpoint: ws://localhost%s/ws/market", listenAddr)

	if err := http.ListenAndServe(listenAddr, nil); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
