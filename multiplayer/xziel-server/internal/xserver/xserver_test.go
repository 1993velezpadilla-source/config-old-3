package xserver

import (
	"testing"
	"time"
)

func TestSortTicketsPrefersHostPriorityThenJoinTime(t *testing.T) {
	now := time.Now()
	tickets := []*matchTicket{
		{playerID: "ci-first", hostPriority: 0, joinedAt: now},
		{playerID: "human-later", hostPriority: 1, joinedAt: now.Add(time.Second)},
		{playerID: "human-earlier", hostPriority: 1, joinedAt: now.Add(500 * time.Millisecond)},
	}
	sortTickets(tickets)
	got := []string{tickets[0].playerID, tickets[1].playerID, tickets[2].playerID}
	want := []string{"human-earlier", "human-later", "ci-first"}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("order[%d]=%q want %q; full=%v", i, got[i], want[i], got)
		}
	}
}

func TestSanitizeTarget(t *testing.T) {
	if sanitizeTarget("2") != 2 || sanitizeTarget("3") != 3 || sanitizeTarget("4") != 4 {
		t.Fatal("valid target player counts were not preserved")
	}
	if got := sanitizeTarget("99"); got != 4 {
		t.Fatalf("invalid target=%d want 4", got)
	}
}

func TestRoomCodeShape(t *testing.T) {
	for i := 0; i < 100; i++ {
		code := randomRoomCode()
		if len(code) != 6 {
			t.Fatalf("room code len=%d code=%q", len(code), code)
		}
		for _, r := range code {
			if !containsRune(roomCodeChars, r) {
				t.Fatalf("room code contains unsupported rune %q in %q", r, code)
			}
		}
	}
}

func containsRune(s string, target rune) bool {
	for _, r := range s {
		if r == target {
			return true
		}
	}
	return false
}
