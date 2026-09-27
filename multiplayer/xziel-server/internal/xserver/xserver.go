package xserver

import (
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/gorilla/websocket"
)

const (
	maxPlayers      = 4
	defaultMap      = "ndu"
	roomCodeChars   = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	maxVoicePacket  = 4096
	serverReadyWait = 8 * time.Second
)

type Config struct {
	PublicHost string
	VrilBinary string
	DataDir    string
	LogDir     string
	PortMin    int
	PortMax    int
}

type dedicatedStarter interface {
	Start(context.Context, string, string, int) (*DedicatedInstance, error)
	Close()
}

type Server struct {
	cfg      Config
	logger   *log.Logger
	upgrader websocket.Upgrader
	starter  dedicatedStarter

	roomsMu sync.Mutex
	rooms   map[string]*room

	queueMu sync.Mutex
	queues  map[string][]*matchTicket
}

type room struct {
	mu           sync.Mutex
	code         string
	mapName      string
	mode         string
	target       int
	reservations map[string]int
	players      map[string]*player
	worldPhase   string
	revision     int
	starting     bool
	instance     *DedicatedInstance
}

type player struct {
	id      string
	slot    int
	game    *websocket.Conn
	voice   *websocket.Conn
	gameMu  sync.Mutex
	voiceMu sync.Mutex
	ciReady bool
}

type matchTicket struct {
	playerID     string
	mapName      string
	queue        string
	target       int
	hostPriority int
	joinedAt     time.Time
	conn         *websocket.Conn
	writeMu      sync.Mutex
	matched      bool
}

type processStarter struct {
	cfg    Config
	logger *log.Logger
	mu     sync.Mutex
	ports  map[int]string
	live   map[string]*DedicatedInstance
}

type DedicatedInstance struct {
	Endpoint string
	Port     int
	RoomCode string

	cmd      *exec.Cmd
	logFile  *os.File
	stopOnce sync.Once
	release  func()
}

func New(cfg Config, logger *log.Logger) (*Server, error) {
	if logger == nil {
		logger = log.New(os.Stdout, "xziel-server: ", log.LstdFlags)
	}
	cfg.PublicHost = strings.TrimSpace(cfg.PublicHost)
	cfg.VrilBinary = strings.TrimSpace(cfg.VrilBinary)
	cfg.DataDir = strings.TrimSpace(cfg.DataDir)
	if cfg.LogDir == "" {
		cfg.LogDir = "server-logs"
	}
	if cfg.PublicHost == "" {
		return nil, errors.New("public host is required")
	}
	if cfg.VrilBinary == "" || cfg.DataDir == "" {
		return nil, errors.New("Vril binary and data dir are required")
	}
	if cfg.PortMin < 1024 || cfg.PortMax < cfg.PortMin || cfg.PortMax > 65535 {
		return nil, errors.New("invalid dedicated UDP port range")
	}
	if _, err := os.Stat(cfg.VrilBinary); err != nil {
		return nil, fmt.Errorf("Vril binary: %w", err)
	}
	if info, err := os.Stat(cfg.DataDir); err != nil || !info.IsDir() {
		if err == nil {
			err = errors.New("not a directory")
		}
		return nil, fmt.Errorf("Vril data dir: %w", err)
	}
	starter := &processStarter{
		cfg: cfg,
		logger: logger,
		ports: make(map[int]string),
		live: make(map[string]*DedicatedInstance),
	}
	return &Server{
		cfg: cfg,
		logger: logger,
		starter: starter,
		rooms: make(map[string]*room),
		queues: make(map[string][]*matchTicket),
		upgrader: websocket.Upgrader{
			CheckOrigin: func(*http.Request) bool { return true },
			HandshakeTimeout: 10 * time.Second,
		},
	}, nil
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/api/rooms/create", s.handleCreateRoom)
	mux.HandleFunc("/matchmake", s.handleMatchmake)
	mux.HandleFunc("/game/", s.handleGame)
	mux.HandleFunc("/voice/", s.handleVoice)
	return mux
}

func (s *Server) Close() {
	s.starter.Close()
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok": true,
		"service": "xziel-dedicated",
		"transport": "native-udp-dedicated",
		"maxPlayers": maxPlayers,
		"matchmaking": true,
		"gameplayRelay": false,
	})
}

func (s *Server) handleCreateRoom(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var body map[string]any
	_ = json.NewDecoder(r.Body).Decode(&body)
	playerID := cleanID(stringValue(body["playerId"]))
	mapName := sanitizeMap(stringValue(body["map"]))

	code, err := s.newRoomCode()
	if err != nil {
		http.Error(w, "room allocation failed", http.StatusInternalServerError)
		return
	}
	reservations := map[string]int{}
	if playerID != "" {
		reservations[playerID] = 1
	}
	rm := &room{
		code: code,
		mapName: mapName,
		mode: "private",
		target: maxPlayers,
		reservations: reservations,
		players: make(map[string]*player),
		worldPhase: "lobby",
	}
	s.roomsMu.Lock()
	s.rooms[code] = rm
	s.roomsMu.Unlock()

	writeJSON(w, http.StatusOK, map[string]any{
		"roomCode": code,
		"map": mapName,
		"mode": "private",
		"maxPlayers": maxPlayers,
		"serverMode": "dedicated",
	})
}

func (s *Server) handleMatchmake(w http.ResponseWriter, r *http.Request) {
	if !websocket.IsWebSocketUpgrade(r) {
		http.Error(w, "upgrade required", http.StatusUpgradeRequired)
		return
	}
	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}

	ticket := &matchTicket{
		playerID: cleanID(r.URL.Query().Get("playerId")),
		mapName: sanitizeMap(r.URL.Query().Get("map")),
		queue: sanitizeQueue(r.URL.Query().Get("queue")),
		target: sanitizeTarget(r.URL.Query().Get("players")),
		hostPriority: sanitizePriority(r.URL.Query().Get("hostPriority")),
		joinedAt: time.Now(),
		conn: conn,
	}
	if ticket.playerID == "" {
		ticket.playerID = "anon-" + randomToken(12)
	}
	key := queueKey(ticket.queue, ticket.mapName, ticket.target)

	s.queueMu.Lock()
	q := s.queues[key]
	filtered := q[:0]
	for _, existing := range q {
		if existing.playerID != ticket.playerID {
			filtered = append(filtered, existing)
		} else {
			existing.safeClose(1000, "replaced")
		}
	}
	s.queues[key] = append(filtered, ticket)
	s.queueMu.Unlock()

	s.broadcastQueueStatus(key)
	s.tryCreateMatches(key)

	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
	s.removeTicket(key, ticket)
}

func (s *Server) tryCreateMatches(key string) {
	for {
		s.queueMu.Lock()
		q := append([]*matchTicket(nil), s.queues[key]...)
		if len(q) == 0 {
			s.queueMu.Unlock()
			return
		}
		sortTickets(q)
		target := q[0].target
		if len(q) < target {
			s.queueMu.Unlock()
			return
		}
		group := append([]*matchTicket(nil), q[:target]...)
		selected := make(map[*matchTicket]bool, len(group))
		for _, t := range group {
			selected[t] = true
			t.matched = true
		}
		remaining := make([]*matchTicket, 0, len(q)-len(group))
		for _, t := range s.queues[key] {
			if !selected[t] {
				remaining = append(remaining, t)
			}
		}
		s.queues[key] = remaining
		s.queueMu.Unlock()

		code, err := s.newRoomCode()
		if err != nil {
			for _, t := range group {
				t.safeJSON(map[string]any{"type": "error", "error": "room_allocation"})
				t.safeClose(1011, "room allocation failed")
			}
			continue
		}
		reservations := make(map[string]int, target)
		for i, t := range group {
			reservations[t.playerID] = i + 1
		}
		rm := &room{
			code: code,
			mapName: group[0].mapName,
			mode: "public",
			target: target,
			reservations: reservations,
			players: make(map[string]*player),
			worldPhase: "lobby",
		}
		s.roomsMu.Lock()
		s.rooms[code] = rm
		s.roomsMu.Unlock()

		for _, t := range group {
			t.safeJSON(map[string]any{
				"type": "match_found",
				"roomCode": code,
				"map": rm.mapName,
				"mode": "public",
				"targetPlayers": target,
				"maxPlayers": target,
				"serverMode": "dedicated",
			})
			t.safeClose(1000, "matched")
		}
		s.logger.Printf("match formed room=%s map=%s players=%d", code, rm.mapName, target)
		s.broadcastQueueStatus(key)
	}
}

func (s *Server) broadcastQueueStatus(key string) {
	s.queueMu.Lock()
	q := append([]*matchTicket(nil), s.queues[key]...)
	s.queueMu.Unlock()
	if len(q) == 0 {
		return
	}
	sortTickets(q)
	for _, t := range q {
		t.safeJSON(map[string]any{
			"type": "searching",
			"map": t.mapName,
			"targetPlayers": t.target,
			"queued": len(q),
			"needed": t.target,
		})
	}
}

func (s *Server) removeTicket(key string, ticket *matchTicket) {
	s.queueMu.Lock()
	q := s.queues[key]
	out := q[:0]
	for _, t := range q {
		if t != ticket {
			out = append(out, t)
		}
	}
	s.queues[key] = out
	s.queueMu.Unlock()
	s.broadcastQueueStatus(key)
}

func sortTickets(q []*matchTicket) {
	sort.SliceStable(q, func(i, j int) bool {
		if q[i].hostPriority != q[j].hostPriority {
			return q[i].hostPriority > q[j].hostPriority
		}
		return q[i].joinedAt.Before(q[j].joinedAt)
	})
}

func (s *Server) handleGame(w http.ResponseWriter, r *http.Request) {
	code := strings.ToUpper(strings.TrimPrefix(r.URL.Path, "/game/"))
	rm := s.lookupRoom(code)
	if rm == nil {
		http.Error(w, "room not found", http.StatusNotFound)
		return
	}
	playerID := cleanID(r.URL.Query().Get("playerId"))
	if playerID == "" {
		playerID = "anon-" + randomToken(12)
	}

	rm.mu.Lock()
	existing := rm.players[playerID]
	if existing == nil && !roomHasFreeSlotLocked(rm) {
		rm.mu.Unlock()
		http.Error(w, "room full", http.StatusConflict)
		return
	}
	rm.mu.Unlock()

	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}

	rm.mu.Lock()
	p := rm.players[playerID]
	if p == nil {
		slot := allocateSlotLocked(rm, playerID)
		if slot == 0 {
			rm.mu.Unlock()
			_ = conn.Close()
			return
		}
		p = &player{id: playerID, slot: slot}
		rm.players[playerID] = p
	}
	oldGame := p.game
	p.game = conn
	p.ciReady = false
	roster := connectedSlotsLocked(rm)
	phase := rm.worldPhase
	revision := rm.revision
	endpoint := ""
	if rm.instance != nil {
		endpoint = rm.instance.Endpoint
	}
	mode := rm.mode
	target := rm.target
	mapName := rm.mapName
	slot := p.slot
	rm.mu.Unlock()

	if oldGame != nil && oldGame != conn {
		_ = oldGame.Close()
	}

	p.sendGameJSON(map[string]any{
		"type": "welcome",
		"roomCode": code,
		"playerId": playerID,
		"slot": slot,
		"players": roster,
		"map": mapName,
		"mode": mode,
		"targetPlayers": target,
		"maxPlayers": target,
		"hostSlot": 0,
		"serverMode": "dedicated",
		"endpoint": endpoint,
		"worldPhase": phase,
		"worldRevision": revision,
		"serverTime": time.Now().UnixMilli(),
	})
	s.broadcastGame(rm, map[string]any{
		"type": "player_joined",
		"playerId": playerID,
		"slot": slot,
		"map": mapName,
		"mode": mode,
		"targetPlayers": target,
	}, playerID)

	if phase == "preparing" {
		p.sendGameJSON(map[string]any{
			"type": "prepare_game",
			"map": mapName,
			"serverMode": "dedicated",
			"worldPhase": phase,
			"worldRevision": revision,
			"replay": true,
		})
	} else if phase == "live" && endpoint != "" {
		p.sendGameJSON(map[string]any{
			"type": "server_ready",
			"map": mapName,
			"serverMode": "dedicated",
			"endpoint": endpoint,
			"worldPhase": phase,
			"worldRevision": revision,
			"replay": true,
		})
	}

	if mode == "public" && len(roster) >= target {
		s.broadcastGame(rm, map[string]any{
			"type": "room_full",
			"map": mapName,
			"mode": mode,
			"players": len(roster),
			"targetPlayers": target,
			"serverMode": "dedicated",
		}, "")
		go s.startDedicated(rm)
	}

	for {
		messageType, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}
		if messageType != websocket.TextMessage || len(payload) > 32768 {
			continue
		}
		var msg map[string]any
		if json.Unmarshal(payload, &msg) != nil {
			continue
		}
		msgType := stringValue(msg["type"])
		switch msgType {
		case "start_match":
			if slot == 1 {
				go s.startDedicated(rm)
			}
		case "client_ready", "ci_action":
			msg["playerId"] = playerID
			msg["slot"] = slot
			msg["serverTime"] = time.Now().UnixMilli()
			s.broadcastGame(rm, msg, playerID)
		case "ci_ready":
			rm.mu.Lock()
			p.ciReady = true
			ready := 0
			for _, candidate := range rm.players {
				if candidate.game != nil && candidate.ciReady {
					ready++
				}
			}
			required := rm.target
			rm.mu.Unlock()
			if ready >= required {
				s.broadcastGame(rm, map[string]any{
					"type": "ci_begin",
					"players": required,
					"serverTime": time.Now().UnixMilli(),
				}, "")
			}
		}
	}

	rm.mu.Lock()
	if p.game == conn {
		p.game = nil
		p.ciReady = false
	}
	remaining := len(connectedSlotsLocked(rm))
	rm.mu.Unlock()
	s.broadcastGame(rm, map[string]any{
		"type": "player_left",
		"playerId": playerID,
		"slot": slot,
	}, playerID)
	if remaining == 0 {
		go s.stopRoomLater(rm, 30*time.Second)
	}
}

func (s *Server) handleVoice(w http.ResponseWriter, r *http.Request) {
	code := strings.ToUpper(strings.TrimPrefix(r.URL.Path, "/voice/"))
	rm := s.lookupRoom(code)
	if rm == nil {
		http.Error(w, "room not found", http.StatusNotFound)
		return
	}
	playerID := cleanID(r.URL.Query().Get("playerId"))
	rm.mu.Lock()
	p := rm.players[playerID]
	valid := p != nil && p.game != nil
	rm.mu.Unlock()
	if !valid {
		http.Error(w, "join game socket first", http.StatusForbidden)
		return
	}
	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}

	rm.mu.Lock()
	oldVoice := p.voice
	p.voice = conn
	slot := p.slot
	rm.mu.Unlock()
	if oldVoice != nil && oldVoice != conn {
		_ = oldVoice.Close()
	}
	p.sendVoiceJSON(map[string]any{
		"type": "voice_ready",
		"roomCode": code,
		"playerId": playerID,
		"slot": slot,
		"serverTime": time.Now().UnixMilli(),
	})

	for {
		messageType, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}
		if messageType != websocket.BinaryMessage ||
			len(payload) <= 24 || len(payload) > maxVoicePacket {
			continue
		}
		if payload[0] != 'X' || payload[1] != 'V' ||
			payload[2] != 'C' || payload[3] != '1' {
			continue
		}
		forwarded := append([]byte(nil), payload...)
		forwarded[4] = byte(slot)
		rm.mu.Lock()
		peers := make([]*player, 0, len(rm.players))
		for _, candidate := range rm.players {
			if candidate != p && candidate.voice != nil {
				peers = append(peers, candidate)
			}
		}
		rm.mu.Unlock()
		for _, peer := range peers {
			peer.sendVoiceBinary(forwarded)
		}
	}
	rm.mu.Lock()
	if p.voice == conn {
		p.voice = nil
	}
	rm.mu.Unlock()
}

func (s *Server) startDedicated(rm *room) {
	rm.mu.Lock()
	if rm.starting || rm.instance != nil || rm.worldPhase == "live" {
		rm.mu.Unlock()
		return
	}
	rm.starting = true
	rm.worldPhase = "preparing"
	rm.revision++
	revision := rm.revision
	mapName := rm.mapName
	target := rm.target
	code := rm.code
	rm.mu.Unlock()

	s.broadcastGame(rm, map[string]any{
		"type": "prepare_game",
		"map": mapName,
		"serverMode": "dedicated",
		"worldPhase": "preparing",
		"worldRevision": revision,
	}, "")

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	instance, err := s.starter.Start(ctx, code, mapName, target)
	if err != nil {
		rm.mu.Lock()
		rm.starting = false
		rm.worldPhase = "lobby"
		rm.mu.Unlock()
		s.logger.Printf("dedicated start failed room=%s: %v", code, err)
		s.broadcastGame(rm, map[string]any{
			"type": "server_error",
			"error": "dedicated_start_failed",
		}, "")
		return
	}

	rm.mu.Lock()
	rm.instance = instance
	rm.starting = false
	rm.worldPhase = "live"
	endpoint := instance.Endpoint
	rm.mu.Unlock()

	s.logger.Printf("dedicated ready room=%s endpoint=%s map=%s", code, endpoint, mapName)
	s.broadcastGame(rm, map[string]any{
		"type": "server_ready",
		"map": mapName,
		"serverMode": "dedicated",
		"endpoint": endpoint,
		"worldPhase": "live",
		"worldRevision": revision,
	}, "")
}

func (s *Server) stopRoomLater(rm *room, delay time.Duration) {
	time.Sleep(delay)
	rm.mu.Lock()
	if len(connectedSlotsLocked(rm)) != 0 || rm.instance == nil {
		rm.mu.Unlock()
		return
	}
	instance := rm.instance
	rm.instance = nil
	rm.worldPhase = "lobby"
	rm.starting = false
	rm.mu.Unlock()
	instance.Stop()
	s.logger.Printf("dedicated stopped room=%s after idle timeout", rm.code)
}

func (s *Server) broadcastGame(rm *room, value map[string]any, exceptID string) {
	value["serverTime"] = time.Now().UnixMilli()
	rm.mu.Lock()
	players := make([]*player, 0, len(rm.players))
	for _, p := range rm.players {
		if p.game != nil && p.id != exceptID {
			players = append(players, p)
		}
	}
	rm.mu.Unlock()
	for _, p := range players {
		p.sendGameJSON(value)
	}
}

func (s *Server) lookupRoom(code string) *room {
	s.roomsMu.Lock()
	defer s.roomsMu.Unlock()
	return s.rooms[code]
}

func (s *Server) newRoomCode() (string, error) {
	for attempt := 0; attempt < 64; attempt++ {
		code := randomRoomCode()
		s.roomsMu.Lock()
		_, exists := s.rooms[code]
		s.roomsMu.Unlock()
		if !exists {
			return code, nil
		}
	}
	return "", errors.New("room code exhaustion")
}

func (p *player) sendGameJSON(value any) {
	p.gameMu.Lock()
	defer p.gameMu.Unlock()
	if p.game != nil {
		_ = p.game.WriteJSON(value)
	}
}

func (p *player) sendVoiceJSON(value any) {
	p.voiceMu.Lock()
	defer p.voiceMu.Unlock()
	if p.voice != nil {
		_ = p.voice.WriteJSON(value)
	}
}

func (p *player) sendVoiceBinary(payload []byte) {
	p.voiceMu.Lock()
	defer p.voiceMu.Unlock()
	if p.voice != nil {
		_ = p.voice.WriteMessage(websocket.BinaryMessage, payload)
	}
}

func (t *matchTicket) safeJSON(value any) {
	t.writeMu.Lock()
	defer t.writeMu.Unlock()
	if t.conn != nil {
		_ = t.conn.WriteJSON(value)
	}
}

func (t *matchTicket) safeClose(code int, reason string) {
	t.writeMu.Lock()
	defer t.writeMu.Unlock()
	if t.conn != nil {
		_ = t.conn.WriteControl(
			websocket.CloseMessage,
			websocket.FormatCloseMessage(code, reason),
			time.Now().Add(time.Second),
		)
		_ = t.conn.Close()
	}
}

func (p *processStarter) Start(ctx context.Context, roomCode, mapName string, players int) (*DedicatedInstance, error) {
	port, err := p.reservePort(roomCode)
	if err != nil {
		return nil, err
	}
	release := func() {
		p.mu.Lock()
		delete(p.ports, port)
		delete(p.live, roomCode)
		p.mu.Unlock()
	}

	if err := os.MkdirAll(p.cfg.LogDir, 0755); err != nil {
		release()
		return nil, err
	}
	logPath := filepath.Join(p.cfg.LogDir, roomCode+"-"+strconv.Itoa(port)+".log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		release()
		return nil, err
	}

	args := []string{
		"-dedicated", strconv.Itoa(players),
		"+vid_renderer", "headless",
		"-basedir", p.cfg.DataDir,
		"-port", strconv.Itoa(port),
		"+maxplayers", strconv.Itoa(players),
		"+coop", "1",
		"+deathmatch", "0",
		"+map", sanitizeMap(mapName),
	}
	cmd := exec.Command(p.cfg.VrilBinary, args...)
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.Env = append(os.Environ(), "SDL_AUDIODRIVER=dummy")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		_ = logFile.Close()
		release()
		return nil, err
	}

	instance := &DedicatedInstance{
		Endpoint: net.JoinHostPort(p.cfg.PublicHost, strconv.Itoa(port)),
		Port: port,
		RoomCode: roomCode,
		cmd: cmd,
		logFile: logFile,
		release: release,
	}
	p.mu.Lock()
	p.live[roomCode] = instance
	p.mu.Unlock()

	waitDone := make(chan error, 1)
	go func() {
		err := cmd.Wait()
		_ = logFile.Close()
		instance.stopOnce.Do(release)
		waitDone <- err
	}()

	deadline := time.Now().Add(serverReadyWait)
	for time.Now().Before(deadline) {
		select {
		case err := <-waitDone:
			if err == nil {
				err = errors.New("dedicated server exited during startup")
			}
			return nil, err
		default:
		}
		if !udpPortFree(port) {
			p.logger.Printf("Vril dedicated bound UDP %d room=%s", port, roomCode)
			return instance, nil
		}
		select {
		case <-ctx.Done():
			instance.Stop()
			return nil, ctx.Err()
		case <-time.After(100 * time.Millisecond):
		}
	}
	instance.Stop()
	return nil, fmt.Errorf("Vril dedicated did not bind UDP %d before timeout", port)
}

func (p *processStarter) reservePort(roomCode string) (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	for port := p.cfg.PortMin; port <= p.cfg.PortMax; port++ {
		if _, used := p.ports[port]; used {
			continue
		}
		if !udpPortFree(port) {
			continue
		}
		p.ports[port] = roomCode
		return port, nil
	}
	return 0, errors.New("no dedicated UDP ports available")
}

func (p *processStarter) Close() {
	p.mu.Lock()
	instances := make([]*DedicatedInstance, 0, len(p.live))
	for _, instance := range p.live {
		instances = append(instances, instance)
	}
	p.mu.Unlock()
	for _, instance := range instances {
		instance.Stop()
	}
}

func (i *DedicatedInstance) Stop() {
	i.stopOnce.Do(func() {
		if i.cmd != nil && i.cmd.Process != nil && i.cmd.Process.Pid > 0 {
			_ = syscall.Kill(-i.cmd.Process.Pid, syscall.SIGTERM)
			time.Sleep(250 * time.Millisecond)
			_ = syscall.Kill(-i.cmd.Process.Pid, syscall.SIGKILL)
		}
		if i.logFile != nil {
			_ = i.logFile.Close()
		}
		if i.release != nil {
			i.release()
		}
	})
}

func udpPortFree(port int) bool {
	conn, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4zero, Port: port})
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}

func roomHasFreeSlotLocked(rm *room) bool {
	used := make(map[int]bool)
	for _, p := range rm.players {
		used[p.slot] = true
	}
	for slot := 1; slot <= rm.target; slot++ {
		if !used[slot] {
			return true
		}
	}
	return false
}

func allocateSlotLocked(rm *room, playerID string) int {
	used := make(map[int]bool)
	for _, p := range rm.players {
		used[p.slot] = true
	}
	if reserved := rm.reservations[playerID]; reserved >= 1 &&
		reserved <= rm.target && !used[reserved] {
		return reserved
	}
	reservedSlots := make(map[int]bool)
	for id, slot := range rm.reservations {
		if id != playerID {
			reservedSlots[slot] = true
		}
	}
	for slot := 1; slot <= rm.target; slot++ {
		if !used[slot] && !reservedSlots[slot] {
			return slot
		}
	}
	for slot := 1; slot <= rm.target; slot++ {
		if !used[slot] {
			return slot
		}
	}
	return 0
}

func connectedSlotsLocked(rm *room) []int {
	slots := make([]int, 0, len(rm.players))
	for _, p := range rm.players {
		if p.game != nil {
			slots = append(slots, p.slot)
		}
	}
	sort.Ints(slots)
	return slots
}

func queueKey(queue, mapName string, target int) string {
	return queue + "|" + mapName + "|" + strconv.Itoa(target)
}

func sanitizeMap(value string) string {
	if strings.EqualFold(strings.TrimSpace(value), defaultMap) {
		return defaultMap
	}
	return defaultMap
}

func sanitizeTarget(value string) int {
	n, _ := strconv.Atoi(value)
	if n == 2 || n == 3 || n == 4 {
		return n
	}
	return maxPlayers
}

func sanitizePriority(value string) int {
	n, _ := strconv.Atoi(value)
	if n > 0 {
		return 1
	}
	return 0
}

func sanitizeQueue(value string) string {
	if value == "" {
		return "public-v1"
	}
	var b strings.Builder
	for _, r := range value {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') ||
			(r >= '0' && r <= '9') || r == '_' || r == '-' {
			b.WriteRune(r)
		}
		if b.Len() >= 64 {
			break
		}
	}
	if b.Len() == 0 {
		return "public-v1"
	}
	return b.String()
}

func cleanID(value string) string {
	value = strings.TrimSpace(value)
	if len(value) > 64 {
		value = value[:64]
	}
	return value
}

func randomRoomCode() string {
	raw := make([]byte, 6)
	if _, err := rand.Read(raw); err != nil {
		return "XZ" + strings.ToUpper(randomToken(4))
	}
	out := make([]byte, 6)
	for i, b := range raw {
		out[i] = roomCodeChars[int(b)%len(roomCodeChars)]
	}
	return string(out)
}

func randomToken(n int) string {
	raw := make([]byte, n)
	if _, err := rand.Read(raw); err != nil {
		return strconv.FormatInt(time.Now().UnixNano(), 36)
	}
	const chars = "abcdefghijklmnopqrstuvwxyz0123456789"
	out := make([]byte, n)
	for i, b := range raw {
		out[i] = chars[int(b)%len(chars)]
	}
	return string(out)
}

func stringValue(value any) string {
	if value == nil {
		return ""
	}
	if s, ok := value.(string); ok {
		return s
	}
	return fmt.Sprint(value)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("content-type", "application/json")
	w.Header().Set("cache-control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
