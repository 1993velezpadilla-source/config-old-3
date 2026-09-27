package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/1993velezpadilla-source/config-old-3/multiplayer/xziel-server/internal/xserver"
)

func envOr(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func envInt(name string, fallback int) int {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func main() {
	logger := log.New(os.Stdout, "xziel-server: ", log.Ldate|log.Ltime|log.LUTC|log.Lmicroseconds)

	listen := flag.String("listen", envOr("XZIEL_CONTROL_LISTEN", ":8080"), "HTTP/WebSocket control listen address")
	publicHost := flag.String("public-host", envOr("XZIEL_PUBLIC_HOST", ""), "public IPv4/hostname advertised for dedicated UDP")
	vrilBin := flag.String("vril-bin", envOr("XZIEL_VRIL_SERVER_BIN", ""), "path to Vril SDL dedicated binary")
	dataDir := flag.String("data-dir", envOr("XZIEL_VRIL_DATA_DIR", ""), "Vril basedir containing nzp/")
	logDir := flag.String("log-dir", envOr("XZIEL_SERVER_LOG_DIR", "server-logs"), "dedicated server log directory")
	portMin := flag.Int("port-min", envInt("XZIEL_GAME_PORT_MIN", 26000), "first dedicated UDP port")
	portMax := flag.Int("port-max", envInt("XZIEL_GAME_PORT_MAX", 26099), "last dedicated UDP port")
	flag.Parse()

	cfg := xserver.Config{
		PublicHost: *publicHost,
		VrilBinary: *vrilBin,
		DataDir:    *dataDir,
		LogDir:     *logDir,
		PortMin:    *portMin,
		PortMax:    *portMax,
	}
	service, err := xserver.New(cfg, logger)
	if err != nil {
		logger.Fatalf("configure: %v", err)
	}

	httpServer := &http.Server{
		Addr:              *listen,
		Handler:           service.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       90 * time.Second,
	}

	go func() {
		logger.Printf("control plane listening on %s; gameplay=%s UDP %d-%d",
			*listen, cfg.PublicHost, cfg.PortMin, cfg.PortMax)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatalf("serve: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	service.Close()
	if err := httpServer.Shutdown(ctx); err != nil {
		logger.Printf("HTTP shutdown: %v", err)
	}
}
