package org.libsdl.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.provider.Settings;
import android.text.InputFilter;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import okio.ByteString;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * Xziel internet multiplayer transport.
 *
 * Cloudflare owns private rooms/public matchmaking and WebSocket routing.
 * Vril keeps its native Quake datagram protocol unchanged: raw UDP datagrams
 * are wrapped in XZD1 and routed between virtual 10.77.0.x peers.
 */
public final class XzielMultiplayer {
    private static final String TAG = "XzielOnline";
    private static final int MAX_PLAYERS = 4;
    private static final int GAME_HEADER_BYTES = 9;
    // Vril MAX_DATAGRAM is 8000 plus its 8-byte network header. Keep a
    // power-of-two ceiling above NET_DATAGRAMSIZE so reliable signon chunks
    // (model/sound precache included) are never rejected by the bridge.
    private static final int MAX_GAME_DATAGRAM = 8192;
    private static final int MAX_QUEUE_PER_PORT = 256;
    private static final long CONNECT_RETRY_MS = 3000L;
    private static final String DEFAULT_MAP = "ndu";
    private static final MediaType JSON =
        MediaType.parse("application/json; charset=utf-8");

    private final Activity activity;
    private final OkHttpClient http;
    private final XzielVoiceChat voiceChat;
    private final ConcurrentHashMap<Integer, ConcurrentLinkedQueue<GamePacket>> packetsByPort =
        new ConcurrentHashMap<>();
    private final Set<Integer> connectedSlots = ConcurrentHashMap.newKeySet();
    private final AtomicReference<String> pendingNativeCommand =
        new AtomicReference<>("");
    // CI-only bounded transport tracing. These counters never affect routing;
    // they only prove which edge of the native UDP <-> WebSocket bridge saw
    // the first few Quake datagrams.
    private volatile int gameTxTraceCount;
    private volatile int gameRxTraceCount;
    private volatile int gamePollTraceCount;

    private volatile String baseUrl;
    private volatile String roomCode = "";
    private volatile String roomMode = "private";
    private volatile String selectedMap = DEFAULT_MAP;
    private volatile int targetPlayers = MAX_PLAYERS;
    private volatile String playerId;
    private volatile int localSlot;
    private volatile WebSocket gameSocket;
    private volatile WebSocket matchSocket;
    private volatile AlertDialog activeDialog;
    private volatile AlertDialog matchmakingDialog;
    private volatile boolean matchmakingActive;
    private volatile String matchmakingQueue = "public-v1";

    private volatile boolean matchStarted;
    private volatile boolean hostPreparing;
    private volatile boolean serverReadySent;
    private volatile boolean serverReadyReceived;
    private volatile String worldPhase = "lobby";
    private volatile int worldRevision;
    private volatile boolean clientReadySent;
    private volatile boolean engineServerActive;
    private volatile boolean engineClientConnected;
    private volatile int engineSignon;
    private volatile String engineMap = "";
    private volatile long lastConnectAttemptMs;
    private volatile boolean gameSocketConnecting;

    private volatile boolean ciEvidenceMode;
    private volatile boolean ciEvidenceDoneSent;
    private volatile boolean ciReadySent;
    private volatile boolean ciScenarioStarted;
    private final boolean[] ciRemoteSeen = new boolean[MAX_PLAYERS + 1];
    private final float[] ciRemoteX = new float[MAX_PLAYERS + 1];
    private final float[] ciRemoteY = new float[MAX_PLAYERS + 1];
    private final float[] ciRemoteZ = new float[MAX_PLAYERS + 1];
    private final int[] ciRemoteFrame = new int[MAX_PLAYERS + 1];

    private static final class GamePacket {
        final int sourceSlot;
        final int sourcePort;
        final byte[] payload;

        GamePacket(int sourceSlot, int sourcePort, byte[] payload) {
            this.sourceSlot = sourceSlot;
            this.sourcePort = sourcePort;
            this.payload = payload;
        }
    }


    /**
     * Original in-app squad-size icon. No external/copyrighted art is used:
     * rings and player silhouettes are drawn directly with Android Canvas.
     */
    private static final class SquadIconView extends View {
        private final int playerCount;
        private final int accent;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF body = new RectF();

        SquadIconView(Context context, int playerCount, int accent) {
            super(context);
            this.playerCount = playerCount;
            this.accent = accent;
            setMinimumWidth(dp(context, 112));
            setMinimumHeight(dp(context, 112));
            setContentDescription(playerCount == 2 ? "Duo" :
                playerCount == 3 ? "Trio" : "Quad");
        }

        @Override
        protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
            int size = dp(getContext(), 112);
            setMeasuredDimension(
                resolveSize(size, widthMeasureSpec),
                resolveSize(size, heightMeasureSpec)
            );
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float cx = getWidth() * 0.5f;
            float cy = getHeight() * 0.5f;
            float radius = Math.min(getWidth(), getHeight()) * 0.42f;

            paint.setStyle(Paint.Style.FILL);
            paint.setColor(Color.rgb(18, 22, 28));
            canvas.drawCircle(cx, cy, radius, paint);

            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(dp(getContext(), 4));
            paint.setColor(accent);
            canvas.drawCircle(cx, cy, radius, paint);
            paint.setStrokeWidth(dp(getContext(), 2));
            paint.setAlpha(145);
            canvas.drawCircle(cx, cy, radius - dp(getContext(), 8), paint);
            paint.setAlpha(255);

            float spacing = radius * (playerCount == 2 ? 0.42f : 0.31f);
            float start = cx - spacing * (playerCount - 1) * 0.5f;
            float headR = radius * (playerCount == 4 ? 0.12f : 0.14f);
            float bodyW = headR * 1.75f;
            float bodyH = headR * 2.1f;

            paint.setStyle(Paint.Style.FILL);
            paint.setColor(Color.WHITE);
            for (int i = 0; i < playerCount; i++) {
                float x = start + spacing * i;
                float headY = cy - radius * 0.16f;
                canvas.drawCircle(x, headY, headR, paint);
                body.set(
                    x - bodyW * 0.5f,
                    headY + headR * 0.70f,
                    x + bodyW * 0.5f,
                    headY + headR * 0.70f + bodyH
                );
                canvas.drawRoundRect(body, headR * 0.55f, headR * 0.55f, paint);
            }

            float badgeR = radius * 0.27f;
            float badgeX = cx - radius * 0.78f;
            float badgeY = cy - radius * 0.78f;
            paint.setColor(Color.rgb(10, 12, 16));
            canvas.drawCircle(badgeX, badgeY, badgeR, paint);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(dp(getContext(), 3));
            paint.setColor(accent);
            canvas.drawCircle(badgeX, badgeY, badgeR, paint);

            paint.setStyle(Paint.Style.FILL);
            paint.setColor(Color.WHITE);
            paint.setTypeface(Typeface.DEFAULT_BOLD);
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTextSize(radius * 0.43f);
            Paint.FontMetrics fm = paint.getFontMetrics();
            float baseline = badgeY - (fm.ascent + fm.descent) * 0.5f;
            canvas.drawText(String.valueOf(playerCount), badgeX, baseline, paint);
        }
    }

    private static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    public XzielMultiplayer(Activity activity, String endpoint) {
        this.activity = activity;
        this.baseUrl = normalizeBaseUrl(endpoint);
        this.playerId = loadPlayerId();
        this.http = new OkHttpClient.Builder()
            .pingInterval(15, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build();
        this.voiceChat = new XzielVoiceChat(
            activity, this.http, this::sendCiEvidenceDone);
    }

    public boolean isOnlineActive() {
        return gameSocket != null && localSlot >= 1 && localSlot <= MAX_PLAYERS;
    }

    public int getLocalSlot() {
        return localSlot;
    }

    public void setCiPlayerId(String value) {
        if (value == null) return;
        String clean = value.replaceAll("[^A-Za-z0-9_-]", "");
        if (!clean.isEmpty() && clean.length() <= 64 &&
            gameSocket == null && matchSocket == null) {
            playerId = clean;
            Log.i(TAG, "CI_PLAYER_ID=" + playerId);
        }
    }

    public void setCiEvidenceMode(boolean enabled) {
        ciEvidenceMode = enabled;
        ciEvidenceDoneSent = false;
        Log.i(TAG, "CI_EVIDENCE_MODE=" + enabled);
    }

    public boolean isCiEvidenceMode() {
        return ciEvidenceMode;
    }

    public void showCiSquadPreview() {
        selectedMap = DEFAULT_MAP;
        targetPlayers = MAX_PLAYERS;
        showPublicSquadSizeMenu();
    }

    public void openMultiplayerMenu() {
        activity.runOnUiThread(() -> {
            if (baseUrl.isEmpty()) {
                Toast.makeText(
                    activity,
                    "This APK was built without the multiplayer backend URL.",
                    Toast.LENGTH_LONG
                ).show();
                return;
            }

            if (isOnlineActive()) {
                showLobbyDialog();
                return;
            }

            showMapSelection();
        });
    }

    private void showMapSelection() {
        activity.runOnUiThread(() -> {
            final String[] labels = { "NACHT DER UNTOTEN" };
            final String[] maps = { "ndu" };
            AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle("SELECT MAP")
                .setMessage("Choose the map first. Solo stays offline from the main menu.")
                .setItems(labels, (d, which) -> {
                    selectedMap = maps[which];
                    showOnlineModeSelection();
                })
                .setNegativeButton("CANCEL", null)
                .create();
            showTracked(dialog);
        });
    }

    private void showOnlineModeSelection() {
        activity.runOnUiThread(() -> {
            AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle(prettyMap(selectedMap))
                .setMessage("How do you want to play this map online?")
                .setPositiveButton("PRIVATE ROOM", (d, w) -> showPrivateMenu())
                .setNegativeButton("PUBLIC MATCH", (d, w) -> showPublicSquadSizeMenu())
                .setNeutralButton("BACK", (d, w) -> showMapSelection())
                .create();
            showTracked(dialog);
        });
    }

    private void showPrivateMenu() {
        activity.runOnUiThread(() -> {
            AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle("PRIVATE ROOM - " + prettyMap(selectedMap))
                .setMessage("Create a room for this map, or join a room code from a friend.")
                .setPositiveButton("CREATE ROOM", (d, w) -> createRoom(selectedMap))
                .setNegativeButton("JOIN ROOM", (d, w) -> showJoinDialog())
                .setNeutralButton("BACK", (d, w) -> showOnlineModeSelection())
                .create();
            showTracked(dialog);
        });
    }

    private void showPublicSquadSizeMenu() {
        activity.runOnUiThread(() -> {
            LinearLayout root = new LinearLayout(activity);
            root.setOrientation(LinearLayout.VERTICAL);
            root.setPadding(dp(activity, 12), dp(activity, 8),
                dp(activity, 12), dp(activity, 4));

            TextView help = new TextView(activity);
            help.setText("Choose how many total players you want in this public match.");
            help.setTextColor(Color.LTGRAY);
            help.setTextSize(15);
            help.setGravity(Gravity.CENTER);
            help.setPadding(0, 0, 0, dp(activity, 8));
            root.addView(help, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ));

            LinearLayout row = new LinearLayout(activity);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER);
            root.addView(row, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ));

            addSquadChoice(row, 2, "DUO", Color.rgb(255, 151, 45));
            addSquadChoice(row, 3, "TRIO", Color.rgb(76, 220, 111));
            addSquadChoice(row, 4, "QUAD", Color.rgb(190, 78, 255));

            AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle("PUBLIC MATCH - " + prettyMap(selectedMap))
                .setView(root)
                .setNegativeButton("BACK", (d, w) -> showOnlineModeSelection())
                .create();
            showTracked(dialog);
        });
    }

    private void addSquadChoice(LinearLayout row, int players,
                                String label, int accent) {
        LinearLayout card = new LinearLayout(activity);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setGravity(Gravity.CENTER);
        card.setPadding(dp(activity, 4), 0, dp(activity, 4), 0);

        SquadIconView icon = new SquadIconView(activity, players, accent);
        card.addView(icon, new LinearLayout.LayoutParams(
            dp(activity, 112), dp(activity, 112)
        ));

        TextView name = new TextView(activity);
        name.setText(label);
        name.setTextColor(Color.WHITE);
        name.setTextSize(18);
        name.setTypeface(Typeface.DEFAULT_BOLD);
        name.setGravity(Gravity.CENTER);
        card.addView(name, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        TextView detail = new TextView(activity);
        detail.setText(players == 2 ? "YOU + 1  •  FIND MATCH" :
            players == 3 ? "YOU + 2  •  FIND MATCH" :
            "YOU + 3  •  FIND MATCH");
        detail.setTextColor(accent);
        detail.setTextSize(11);
        detail.setGravity(Gravity.CENTER);
        card.addView(detail, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        card.setOnClickListener(v -> {
            dismissTrackedDialog();
            findPublicMatch(selectedMap, players, "public-v1");
        });

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f
        );
        row.addView(card, params);
    }

    private void showJoinDialog() {
        activity.runOnUiThread(() -> {
            EditText input = new EditText(activity);
            input.setSingleLine(true);
            input.setHint("6-CHARACTER ROOM CODE");
            input.setAllCaps(true);
            input.setFilters(new InputFilter[] { new InputFilter.LengthFilter(6) });

            AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle("JOIN PRIVATE ROOM")
                .setView(input)
                .setPositiveButton("JOIN", null)
                .setNegativeButton("BACK", (d, w) -> showPrivateMenu())
                .create();

            dialog.setOnShowListener(v -> {
                dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(button -> {
                    String code = input.getText().toString().trim().toUpperCase(Locale.US);
                    if (!code.matches("[A-HJ-NP-Z2-9]{6}")) {
                        input.setError("Enter the 6-character room code");
                        return;
                    }
                    dialog.dismiss();
                    activeDialog = null;
                    joinRoom(code, false);
                });

                input.requestFocus();
                InputMethodManager imm = (InputMethodManager)
                    activity.getSystemService(Context.INPUT_METHOD_SERVICE);
                if (imm != null) {
                    imm.showSoftInput(input, InputMethodManager.SHOW_IMPLICIT);
                }
            });

            showTracked(dialog);
        });
    }

    private void createRoom(String map) {
        JSONObject body = new JSONObject();
        try {
            body.put("playerId", playerId);
            body.put("map", map);
        } catch (Exception ignored) {}

        Request request = new Request.Builder()
            .url(baseUrl + "/api/rooms/create")
            .post(RequestBody.create(body.toString(), JSON))
            .build();

        toast("Creating private room...");
        http.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, java.io.IOException e) {
                toast("Could not reach multiplayer service");
            }

            @Override
            public void onResponse(Call call, Response response) {
                try (Response r = response) {
                    if (!r.isSuccessful() || r.body() == null) {
                        toast("Room creation failed (" + r.code() + ")");
                        return;
                    }

                    JSONObject answer = new JSONObject(r.body().string());
                    String code = answer.optString("roomCode", "");
                    if (code.length() != 6) {
                        toast("Server returned an invalid room");
                        return;
                    }
                    selectedMap = answer.optString("map", DEFAULT_MAP);
                    joinRoom(code, false);
                } catch (Exception e) {
                    toast("Could not read room response");
                }
            }
        });
    }

    public void findPublicMatch() {
        findPublicMatch(DEFAULT_MAP, MAX_PLAYERS, "public-v1");
    }

    public void findPublicMatch(String queueName) {
        findPublicMatch(DEFAULT_MAP, MAX_PLAYERS, queueName);
    }

    public void findPublicMatch(String map, int players, String queueName) {
        cancelMatchmaking();
        leaveGameRoomOnly();

        selectedMap = map == null || map.isEmpty() ? DEFAULT_MAP : map;
        targetPlayers = players == 2 || players == 3 || players == 4
            ? players : MAX_PLAYERS;
        roomMode = "public";

        String queue = queueName == null ? "public-v1"
            : queueName.replaceAll("[^A-Za-z0-9_-]", "");
        if (queue.isEmpty()) queue = "public-v1";

        matchmakingQueue = queue;
        matchmakingActive = true;
        showMatchmakingSearchDialog();
        openMatchmakingSocket();
    }

    private void openMatchmakingSocket() {
        if (!matchmakingActive || matchSocket != null) return;

        String wsUrl = websocketBase() + "/matchmake?playerId=" + playerId +
            "&map=" + selectedMap + "&players=" + targetPlayers +
            "&queue=" + matchmakingQueue;
        Request request = new Request.Builder().url(wsUrl).build();

        Log.i(TAG, "MATCH_CONNECT queue=" + matchmakingQueue +
            " map=" + selectedMap + " targetPlayers=" + targetPlayers);

        final WebSocket socket = http.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket webSocket, Response response) {
                if (!matchmakingActive) {
                    try { webSocket.close(1000, "cancelled"); } catch (Exception ignored) {}
                    return;
                }
                Log.i(TAG, "MATCH_SOCKET_OPEN queue=" + matchmakingQueue +
                    " targetPlayers=" + targetPlayers);
            }

            @Override
            public void onMessage(WebSocket webSocket, String text) {
                if (!matchmakingActive) return;
                try {
                    JSONObject message = new JSONObject(text);
                    String type = message.optString("type", "");
                    if ("searching".equals(type)) {
                        int queued = message.optInt("queued", 1);
                        int needed = message.optInt("needed", targetPlayers);
                        targetPlayers = needed;
                        Log.i(TAG, "MATCH_SEARCHING queued=" + queued +
                            " needed=" + needed);
                        updateMatchmakingStatus(queued, needed);
                        return;
                    }
                    if ("match_found".equals(type)) {
                        String code = message.optString("roomCode", "");
                        selectedMap = message.optString("map", DEFAULT_MAP);
                        targetPlayers = message.optInt("targetPlayers", targetPlayers);

                        matchmakingActive = false;
                        if (matchSocket == webSocket) matchSocket = null;
                        matchmakingDialog = null;
                        dismissTrackedDialog();

                        Log.i(TAG, "MATCH_FOUND room=" + code +
                            " targetPlayers=" + targetPlayers);
                        try { webSocket.close(1000, "matched"); } catch (Exception ignored) {}

                        if (code.length() == 6) {
                            toast("Match found - entering room");
                            joinRoom(code, true);
                        }
                    }
                } catch (Exception ignored) {}
            }

            @Override
            public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                if (matchSocket == webSocket) matchSocket = null;
                if (!matchmakingActive) return;

                Log.w(TAG, "MATCH_SOCKET_FAILURE - retrying", t);
                updateMatchmakingReconnectState();
                scheduleMatchmakingReconnect();
            }

            @Override
            public void onClosed(WebSocket webSocket, int code, String reason) {
                if (matchSocket == webSocket) matchSocket = null;
                if (!matchmakingActive) return;

                Log.i(TAG, "MATCH_SOCKET_CLOSED code=" + code +
                    " reason=" + reason + " - retrying");
                updateMatchmakingReconnectState();
                scheduleMatchmakingReconnect();
            }
        });

        if (matchmakingActive) {
            matchSocket = socket;
        } else {
            try { socket.close(1000, "cancelled"); } catch (Exception ignored) {}
        }
    }

    private void scheduleMatchmakingReconnect() {
        activity.getWindow().getDecorView().postDelayed(() -> {
            if (matchmakingActive && matchSocket == null) {
                openMatchmakingSocket();
            }
        }, 1500);
    }

    private void joinRoom(String code, boolean publicMatch) {
        leaveGameRoomOnly();

        roomCode = code;
        roomMode = publicMatch ? "public" : "private";
        localSlot = 0;
        matchStarted = false;
        hostPreparing = false;
        serverReadySent = false;
        serverReadyReceived = false;
        worldPhase = "lobby";
        worldRevision = 0;
        clientReadySent = false;
        ciReadySent = false;
        ciScenarioStarted = false;
        for (int i = 0; i < ciRemoteSeen.length; i++) ciRemoteSeen[i] = false;
        lastConnectAttemptMs = 0;
        connectedSlots.clear();
        packetsByPort.clear();
        gameTxTraceCount = 0;
        gameRxTraceCount = 0;
        gamePollTraceCount = 0;

        toast("Joining room " + code + "...");
        openGameSocket();
    }

    private void openGameSocket() {
        final String expectedRoom = roomCode;
        if (expectedRoom.isEmpty() || gameSocket != null || gameSocketConnecting) {
            return;
        }

        gameSocketConnecting = true;
        String wsUrl = websocketBase() + "/game/" + expectedRoom +
            "?playerId=" + playerId;
        Request request = new Request.Builder().url(wsUrl).build();

        Log.i(TAG, "GAME_CONNECT room=" + expectedRoom +
            " playerId=" + playerId + " mode=" + roomMode);

        final WebSocket socket = http.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket webSocket, Response response) {
                gameSocketConnecting = false;

                if (!expectedRoom.equals(roomCode)) {
                    try { webSocket.close(1000, "stale_room"); } catch (Exception ignored) {}
                    return;
                }

                gameSocket = webSocket;
                Log.i(TAG, "GAME_SOCKET_OPEN room=" + expectedRoom +
                    " status=" + response.code());
                webSocket.send("{\"type\":\"hello\"}");
            }

            @Override
            public void onMessage(WebSocket webSocket, String text) {
                if (gameSocket == webSocket && expectedRoom.equals(roomCode)) {
                    handleControlMessage(text);
                }
            }

            @Override
            public void onMessage(WebSocket webSocket, ByteString bytes) {
                if (gameSocket == webSocket && expectedRoom.equals(roomCode)) {
                    handleGamePacket(bytes.toByteArray());
                }
            }

            @Override
            public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                gameSocketConnecting = false;
                int status = response != null ? response.code() : 0;
                if (gameSocket == webSocket) gameSocket = null;

                Log.w(TAG, "GAME_SOCKET_FAILURE room=" + expectedRoom +
                    " status=" + status + " retrying=" +
                    expectedRoom.equals(roomCode), t);

                if (expectedRoom.equals(roomCode) && !roomCode.isEmpty()) {
                    if (status == 409) {
                        toast("Room is full");
                        leaveGameRoomOnly();
                    } else {
                        scheduleGameSocketReconnect(expectedRoom);
                    }
                }
            }

            @Override
            public void onClosed(WebSocket webSocket, int codeValue, String reason) {
                gameSocketConnecting = false;
                if (gameSocket == webSocket) gameSocket = null;

                Log.i(TAG, "GAME_SOCKET_CLOSED room=" + expectedRoom +
                    " code=" + codeValue + " reason=" + reason);

                if (expectedRoom.equals(roomCode) && !roomCode.isEmpty() &&
                    codeValue != 1000) {
                    scheduleGameSocketReconnect(expectedRoom);
                }
            }
        });
    }

    private void scheduleGameSocketReconnect(String expectedRoom) {
        activity.getWindow().getDecorView().postDelayed(() -> {
            if (expectedRoom.equals(roomCode) && !roomCode.isEmpty() &&
                gameSocket == null && !gameSocketConnecting) {
                Log.i(TAG, "GAME_RECONNECT room=" + expectedRoom);
                openGameSocket();
            }
        }, 1200);
    }

    private void handleControlMessage(String text) {
        try {
            JSONObject message = new JSONObject(text);
            String type = message.optString("type", "");

            if ("welcome".equals(type)) {
                int slot = message.optInt("slot", 0);
                if (slot < 1 || slot > MAX_PLAYERS) {
                    toast("Invalid multiplayer slot");
                    leaveRoom();
                    return;
                }

                localSlot = slot;
                selectedMap = message.optString("map", DEFAULT_MAP);
                roomMode = message.optString("mode", roomMode);
                targetPlayers = message.optInt("targetPlayers",
                    "public".equals(roomMode) ? targetPlayers : MAX_PLAYERS);
                worldPhase = message.optString("worldPhase", "lobby");
                worldRevision = Math.max(0, message.optInt("worldRevision", 0));
                connectedSlots.clear();
                JSONArray roster = message.optJSONArray("players");
                if (roster != null) {
                    for (int i = 0; i < roster.length(); i++) {
                        int playerSlot = roster.optInt(i, 0);
                        if (playerSlot >= 1 && playerSlot <= MAX_PLAYERS) {
                            connectedSlots.add(playerSlot);
                        }
                    }
                }
                connectedSlots.add(slot);

                voiceChat.connect(baseUrl, roomCode, playerId, slot);
                for (int playerSlot : connectedSlots) {
                    voiceChat.setPlayerConnected(playerSlot, true);
                }
                queueNativeCommand("name XzielP" + slot + "\n");
                Log.i(TAG, "WELCOME room=" + roomCode + " mode=" + roomMode +
                    " slot=" + slot + " map=" + selectedMap +
                    " targetPlayers=" + targetPlayers +
                    " world=" + worldRevision + "/" + worldPhase +
                    " roster=" + connectedSlots);
                toast(("public".equals(roomMode) ? "Public match" : "Room " + roomCode) +
                    " - Player " + slot);

                if ("private".equals(roomMode)) {
                    activity.runOnUiThread(this::showLobbyDialog);
                }
                return;
            }

            if ("player_joined".equals(type)) {
                int slot = message.optInt("slot", 0);
                if (slot >= 1 && slot <= MAX_PLAYERS) {
                    connectedSlots.add(slot);
                    voiceChat.setPlayerConnected(slot, true);
                    Log.i(TAG, "PLAYER_JOINED slot=" + slot +
                        " count=" + connectedSlots.size() +
                        " roster=" + connectedSlots);
                    toast("Player " + slot + " connected");
                }
                return;
            }

            if ("player_left".equals(type)) {
                int slot = message.optInt("slot", 0);
                connectedSlots.remove(slot);
                voiceChat.setPlayerConnected(slot, false);
                Log.i(TAG, "PLAYER_LEFT slot=" + slot +
                    " local=" + localSlot +
                    " roster=" + connectedSlots);
                toast("Player " + slot + " left");
                return;
            }

            if ("room_full".equals(type)) {
                if ("public".equals(roomMode) && localSlot == 1 && !hostPreparing) {
                    startHostMatch(true);
                } else if ("public".equals(roomMode)) {
                    toast(targetPlayers + "/" + targetPlayers +
                        " players - starting match...");
                }
                return;
            }

            if ("prepare_game".equals(type) && localSlot != 1) {
                String authoritativeMap = message.optString("map", selectedMap);
                int revision = Math.max(0,
                    message.optInt("worldRevision", worldRevision));

                if (revision < worldRevision) {
                    Log.i(TAG, "IGNORE_STALE_PREPARE slot=" + localSlot +
                        " incoming=" + revision + " current=" + worldRevision);
                    return;
                }

                selectedMap = authoritativeMap;
                worldRevision = revision;
                worldPhase = "preparing";
                matchStarted = true;
                serverReadyReceived = false;
                dismissTrackedDialog();
                Log.i(TAG, "PREPARE_GAME slot=" + localSlot +
                    " map=" + selectedMap +
                    " world=" + worldRevision +
                    " replay=" + message.optBoolean("replay", false));
                toast("Host is loading " + prettyMap(selectedMap) + "...");
                return;
            }

            if ("server_ready".equals(type) && localSlot != 1) {
                String authoritativeMap = message.optString("map", selectedMap);
                int revision = Math.max(0,
                    message.optInt("worldRevision", worldRevision));

                if (revision < worldRevision) {
                    Log.i(TAG, "IGNORE_STALE_SERVER_READY slot=" + localSlot +
                        " incoming=" + revision + " current=" + worldRevision);
                    return;
                }

                selectedMap = authoritativeMap;
                worldRevision = revision;
                worldPhase = "live";
                serverReadyReceived = true;
                matchStarted = true;
                dismissTrackedDialog();
                Log.i(TAG, "SERVER_READY slot=" + localSlot +
                    " map=" + selectedMap +
                    " world=" + worldRevision +
                    " replay=" + message.optBoolean("replay", false));
                beginClientConnection(message.optBoolean("replay", false));
                return;
            }

            if ("client_ready".equals(type) && localSlot == 1) {
                int slot = message.optInt("slot", 0);
                if (slot >= 2 && slot <= MAX_PLAYERS) {
                    Log.i(TAG, "CLIENT_READY host=1 clientSlot=" + slot);
                    toast("Player " + slot + " entered the match");
                }
            }


            if ("ci_begin".equals(type) && ciEvidenceMode && !ciScenarioStarted) {
                ciScenarioStarted = true;
                Log.i(TAG, "CI_BEGIN slot=" + localSlot +
                    " players=" + targetPlayers);
                scheduleCiEvidenceScenario();
                return;
            }

            if ("ci_action".equals(type) && ciEvidenceMode) {
                int remoteSlot = message.optInt("slot", 0);
                String action = message.optString("action", "");
                if (remoteSlot >= 1 && remoteSlot <= MAX_PLAYERS &&
                    remoteSlot != localSlot && !action.isEmpty()) {
                    Log.i(TAG, "CI_REMOTE_ACTION observer=" + localSlot +
                        " remote=" + remoteSlot + " action=" + action);
                }
                return;
            }
        } catch (Exception ignored) {
        }
    }

    private void showLobbyDialog() {
        if (!isOnlineActive()) return;

        activity.runOnUiThread(() -> {
            if (!isOnlineActive()) return;
            boolean host = localSlot == 1;
            String message =
                "ROOM CODE: " + roomCode +
                "\nMAP: " + prettyMap(selectedMap) +
                "\nPLAYER: " + localSlot +
                "\nPLAYERS CONNECTED: " + connectedSlots.size() + "/" + MAX_PLAYERS +
                (host
                    ? "\n\nShare the code. Start when everyone is ready."
                    : "\n\nWaiting for Player 1 to start the match.");

            AlertDialog.Builder builder = new AlertDialog.Builder(activity)
                .setTitle(host ? "PRIVATE ROOM - HOST" : "PRIVATE ROOM")
                .setMessage(message)
                .setNegativeButton("LEAVE ROOM", (d, w) -> leaveRoom())
                .setNeutralButton("CLOSE", null);

            if (host && !matchStarted && !hostPreparing) {
                builder.setPositiveButton("START MATCH", (d, w) -> startHostMatch(false));
            }

            showTracked(builder.create());
        });
    }

    private void startHostMatch(boolean automaticPublicStart) {
        if (localSlot != 1 || hostPreparing || gameSocket == null) return;

        hostPreparing = true;
        matchStarted = true;
        serverReadySent = false;
        serverReadyReceived = false;
        dismissTrackedDialog();

        JSONObject prepare = new JSONObject();
        try {
            prepare.put("type", "prepare_game");
            prepare.put("map", selectedMap);
            gameSocket.send(prepare.toString());
        } catch (Exception ignored) {}

        queueNativeCommand(
            "disconnect\n" +
            "maxplayers " + ("public".equals(roomMode) ? targetPlayers : MAX_PLAYERS) + "\n" +
            "coop 1\n" +
            "deathmatch 0\n" +
            "listen 1\n" +
            "map " + selectedMap + "\n"
        );

        worldPhase = "preparing";
        Log.i(TAG, "HOST_PREPARE mode=" + roomMode + " map=" + selectedMap +
            " targetPlayers=" + targetPlayers +
            " players=" + connectedSlots.size() +
            " authoritativeWorld=true");
        toast((automaticPublicStart ? "Public match ready - " : "Starting ") +
            prettyMap(selectedMap) + "...");
    }

    private void beginClientConnection(boolean retry) {
        if (localSlot <= 1 || gameSocket == null || !serverReadyReceived) return;

        long now = System.currentTimeMillis();
        if (retry && now - lastConnectAttemptMs < CONNECT_RETRY_MS) return;
        lastConnectAttemptMs = now;

        Log.i(TAG, (retry ? "CONNECT_RETRY" : "CONNECT_START") +
            " slot=" + localSlot + " target=10.77.0.1:26000");
        if (retry) {
            queueNativeCommand("disconnect\nconnect 10.77.0.1:26000\n");
            toast("Reconnecting to host...");
        } else {
            queueNativeCommand("connect 10.77.0.1:26000\n");
            toast("Server ready - entering match...");
        }
    }

    /**
     * Called from the native Vril game thread at a low frequency.
     * This closes the old race where clients tried to connect before the host
     * had actually opened its Quake listen socket.
     */
    public void updateVoicePosition(float x, float y, float z) {
        voiceChat.updateLocalPosition(x, y, z);
    }

    public void showVoicePausePanel(boolean visible) {
        Log.i(TAG, "PAUSE_VOICE visible=" + visible +
            " online=" + isOnlineActive() +
            " socket=" + (gameSocket != null) +
            " connecting=" + gameSocketConnecting +
            " local=" + localSlot +
            " roster=" + connectedSlots);
        if (visible) voiceChat.showPausePanel();
        else voiceChat.hidePausePanel();
    }

    public void onMicrophonePermissionResult(boolean granted) {
        voiceChat.onMicrophonePermissionResult(granted);
    }

    public void onEngineState(boolean serverActive, boolean clientConnected,
                              int signon, String map) {
        engineServerActive = serverActive;
        engineClientConnected = clientConnected;
        engineSignon = signon;
        engineMap = map == null ? "" : map;

        if (!isOnlineActive()) return;

        if (localSlot == 1 && hostPreparing && !serverReadySent &&
            serverActive && selectedMap.equals(engineMap)) {
            serverReadySent = true;
            hostPreparing = false;
            worldPhase = "live";

            JSONObject ready = new JSONObject();
            try {
                ready.put("type", "server_ready");
                ready.put("map", selectedMap);
                WebSocket socket = gameSocket;
                if (socket != null) socket.send(ready.toString());
            } catch (Exception ignored) {}

            Log.i(TAG, "HOST_SERVER_READY map=" + selectedMap);
            toast("Server ready - bringing players in");
            if (ciEvidenceMode) sendCiReady();
            return;
        }

        if (localSlot > 1 && serverReadyReceived) {
            // ca_connected with signon 0..3 is the normal Quake handshake /
            // signon progression. Retry engine connection only until this world
            // has completed signon once. After client_ready, a later
            // clientConnected=false can be normal end-of-match teardown; a real
            // transport reconnect is driven by replayed server_ready from the
            // WebSocket room state instead of blindly issuing disconnect/connect.
            if (!clientConnected && !clientReadySent) {
                beginClientConnection(true);
            } else if (signon >= 4 && !clientReadySent) {
                clientReadySent = true;
                JSONObject ready = new JSONObject();
                try {
                    ready.put("type", "client_ready");
                    WebSocket socket = gameSocket;
                    if (socket != null) socket.send(ready.toString());
                } catch (Exception ignored) {}
                Log.i(TAG, "SIGNON_COMPLETE slot=" + localSlot +
                    " signon=" + signon + " map=" + engineMap);
                toast("Connected to match");
                if (ciEvidenceMode) sendCiReady();
            }
        }
    }

    private void sendCiReady() {
        if (!ciEvidenceMode || ciReadySent) return;
        WebSocket socket = gameSocket;
        if (socket == null || localSlot < 1) return;

        ciReadySent = true;
        JSONObject ready = new JSONObject();
        try {
            ready.put("type", "ci_ready");
            socket.send(ready.toString());
            Log.i(TAG, "CI_READY slot=" + localSlot);
        } catch (Exception e) {
            ciReadySent = false;
        }
    }

    private void sendCiEvidenceDone() {
        if (!ciEvidenceMode || ciEvidenceDoneSent || !isOnlineActive()) return;

        WebSocket socket = gameSocket;
        if (socket == null || localSlot < 1 || localSlot > MAX_PLAYERS) return;

        JSONObject action = new JSONObject();
        try {
            action.put("type", "ci_action");
            action.put("action", "CI_EVIDENCE_DONE");
            if (socket.send(action.toString())) {
                ciEvidenceDoneSent = true;
                Log.i(TAG, "CI_EVIDENCE_DONE slot=" + localSlot);
            }
        } catch (Exception ignored) {}
    }

    private void ciCommand(long delayMs, String marker, String command) {
        activity.getWindow().getDecorView().postDelayed(() -> {
            if (!ciEvidenceMode || !isOnlineActive()) return;

            if (command != null && !command.isEmpty()) {
                queueNativeCommand(command);
            }

            if (marker != null && !marker.isEmpty()) {
                Log.i(TAG, marker + " slot=" + localSlot);
                JSONObject action = new JSONObject();
                try {
                    action.put("type", "ci_action");
                    action.put("action", marker);
                    WebSocket socket = gameSocket;
                    if (socket != null) socket.send(action.toString());
                } catch (Exception ignored) {}
            }
        }, delayMs);
    }

    private void scheduleCiEvidenceScenario() {
        // Keep the evidence window alive without changing normal multiplayer.
        // Godmode is a normal server-side client flag in coop, so zombies still
        // target, move, attack and emit their real world audio while CI players
        // cannot end the match before pause/voice/mute evidence is captured.
        ciCommand(50, "CI_GODMODE", "god\n");

        if (localSlot == 1) {
            ciCommand(250, "CI_P1_SPRINT_AWAY",
                "cl_yawspeed 180\nimpulse 23\n+forward\n");
            ciCommand(1450, "CI_P1_TURN_BACK",
                "-forward\nimpulse 24\n+left\n");
            ciCommand(2500, "CI_CAMERA_READY", "-left\n");
            activity.getWindow().getDecorView().postDelayed(() -> {
                if (ciEvidenceMode) voiceChat.sendCiTestTone();
            }, 3400);
            ciCommand(7200, "CI_SCENARIO_DONE", "");
        } else if (localSlot == 2) {
            ciCommand(700, "CI_P2_WALK_START", "+forward\n");
            ciCommand(2200, "CI_P2_WALK_STOP", "-forward\n");
            ciCommand(3100, "CI_P2_AIM_START", "+aim\n");
            activity.getWindow().getDecorView().postDelayed(() -> {
                if (ciEvidenceMode) voiceChat.sendCiTestTone();
            }, 3600);
            ciCommand(4400, "CI_P2_AIM_STOP", "-aim\n");
            ciCommand(7200, "CI_SCENARIO_DONE", "");
        } else if (localSlot == 3) {
            ciCommand(3000, "CI_P3_SPRINT_START", "impulse 23\n+forward\n");
            ciCommand(4000, "CI_P3_SPRINT_STOP", "-forward\nimpulse 24\n");
            ciCommand(4450, "CI_P3_GRENADE_PRIME", "+grenade\n");
            ciCommand(5000, "CI_P3_GRENADE_THROW", "-grenade\n");
            activity.getWindow().getDecorView().postDelayed(() -> {
                if (ciEvidenceMode) voiceChat.sendCiTestTone();
            }, 3800);
            ciCommand(7200, "CI_SCENARIO_DONE", "");
        } else if (localSlot == 4) {
            ciCommand(3000, "CI_P4_AIM_START", "+aim\n");
            ciCommand(3600, "CI_P4_FIRE_START", "+attack\n");
            activity.getWindow().getDecorView().postDelayed(() -> {
                if (ciEvidenceMode) voiceChat.sendCiTestTone();
            }, 4000);
            ciCommand(4300, "CI_P4_FIRE_STOP", "-attack\n");
            ciCommand(4700, "CI_P4_AIM_STOP", "-aim\n");
            ciCommand(7200, "CI_SCENARIO_DONE", "");
        }
    }

    public void onCiRemoteEntity(int slot, float x, float y, float z,
                                 int frame, float yaw) {
        if (!ciEvidenceMode || slot < 1 || slot > MAX_PLAYERS ||
            slot == localSlot) {
            return;
        }

        if (!ciRemoteSeen[slot]) {
            ciRemoteSeen[slot] = true;
            ciRemoteX[slot] = x;
            ciRemoteY[slot] = y;
            ciRemoteZ[slot] = z;
            ciRemoteFrame[slot] = frame;
            Log.i(TAG, "CI_REMOTE_SEEN observer=" + localSlot +
                " remote=" + slot + " frame=" + frame +
                " pos=" + x + "," + y + "," + z + " yaw=" + yaw);
            return;
        }

        float dx = x - ciRemoteX[slot];
        float dy = y - ciRemoteY[slot];
        float dz = z - ciRemoteZ[slot];
        float moved = (float)Math.sqrt(dx * dx + dy * dy + dz * dz);

        if (moved >= 3.0f) {
            Log.i(TAG, "CI_REMOTE_MOVE observer=" + localSlot +
                " remote=" + slot + " delta=" + moved +
                " pos=" + x + "," + y + "," + z);
            ciRemoteX[slot] = x;
            ciRemoteY[slot] = y;
            ciRemoteZ[slot] = z;
        }

        if (frame != ciRemoteFrame[slot]) {
            Log.i(TAG, "CI_REMOTE_FRAME observer=" + localSlot +
                " remote=" + slot + " from=" + ciRemoteFrame[slot] +
                " to=" + frame + " yaw=" + yaw);
            ciRemoteFrame[slot] = frame;
        }
    }

    public void onCiSoundEvent(int entity, int channel, String name,
                               float x, float y, float z) {
        if (!ciEvidenceMode || entity == localSlot) {
            return;
        }

        String sound = name == null ? "" : name;
        // CI only needs proof of networked human footsteps and weapon/grenade
        // audio. Logging every zombie ambient/step sound can flood logcat with
        // hundreds of thousands of lines and hide the actual fatal engine error.
        if (!sound.startsWith("sounds/player/footstep") &&
            !sound.startsWith("sounds/weapons/")) {
            return;
        }

        Log.i(TAG, "CI_REMOTE_SOUND observer=" + localSlot +
            " source=" + entity +
            " channel=" + channel +
            " sound=" + sound +
            " pos=" + x + "," + y + "," + z);
    }

    public boolean sendGameDatagram(byte[] payload, int destinationSlot,
                                    int sourcePort, int destinationPort) {
        WebSocket socket = gameSocket;
        if (socket == null || payload == null ||
            payload.length <= 0 || payload.length > MAX_GAME_DATAGRAM ||
            destinationSlot < 1 || destinationSlot > MAX_PLAYERS ||
            sourcePort < 0 || sourcePort > 65535 ||
            destinationPort < 0 || destinationPort > 65535) {
            if (ciEvidenceMode && payload != null &&
                payload.length > MAX_GAME_DATAGRAM) {
                Log.e(TAG, "GAME_TX_REJECT oversize=" + payload.length +
                    " max=" + MAX_GAME_DATAGRAM +
                    " dst=" + destinationSlot +
                    " srcPort=" + sourcePort +
                    " dstPort=" + destinationPort);
            }
            return false;
        }

        ByteBuffer packet = ByteBuffer
            .allocate(GAME_HEADER_BYTES + payload.length)
            .order(ByteOrder.BIG_ENDIAN);

        packet.put((byte)'X');
        packet.put((byte)'Z');
        packet.put((byte)'D');
        packet.put((byte)'1');
        packet.put((byte)destinationSlot);
        packet.putShort((short)(sourcePort & 0xffff));
        packet.putShort((short)(destinationPort & 0xffff));
        packet.put(payload);

        boolean sent = socket.send(ByteString.of(packet.array()));
        if (ciEvidenceMode && gameTxTraceCount < 16) {
            gameTxTraceCount++;
            Log.i(TAG, "GAME_TX slot=" + localSlot +
                " dst=" + destinationSlot +
                " srcPort=" + sourcePort +
                " dstPort=" + destinationPort +
                " bytes=" + payload.length +
                " accepted=" + sent);
        }
        return sent;
    }

    private void handleGamePacket(byte[] data) {
        if (data == null || data.length <= GAME_HEADER_BYTES) return;

        ByteBuffer packet = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);
        if (packet.get() != 'X' || packet.get() != 'Z' ||
            packet.get() != 'D' || packet.get() != '1') {
            return;
        }

        int sourceSlot = packet.get() & 0xff;
        int sourcePort = packet.getShort() & 0xffff;
        int destinationPort = packet.getShort() & 0xffff;

        if (sourceSlot < 1 || sourceSlot > MAX_PLAYERS ||
            sourceSlot == localSlot || destinationPort <= 0 ||
            packet.remaining() <= 0 || packet.remaining() > MAX_GAME_DATAGRAM) {
            return;
        }

        byte[] payload = new byte[packet.remaining()];
        packet.get(payload);

        if (ciEvidenceMode && gameRxTraceCount < 16) {
            gameRxTraceCount++;
            Log.i(TAG, "GAME_RX slot=" + localSlot +
                " src=" + sourceSlot +
                " srcPort=" + sourcePort +
                " dstPort=" + destinationPort +
                " bytes=" + payload.length);
        }

        ConcurrentLinkedQueue<GamePacket> queue = packetsByPort.computeIfAbsent(
            destinationPort,
            ignored -> new ConcurrentLinkedQueue<>()
        );

        while (queue.size() >= MAX_QUEUE_PER_PORT) {
            queue.poll();
        }
        queue.offer(new GamePacket(sourceSlot, sourcePort, payload));
    }

    public byte[] pollGameDatagram(int localPort) {
        ConcurrentLinkedQueue<GamePacket> queue = packetsByPort.get(localPort);
        if (queue == null) return null;

        GamePacket packet = queue.poll();
        if (packet == null) return null;

        if (ciEvidenceMode && gamePollTraceCount < 16) {
            gamePollTraceCount++;
            Log.i(TAG, "GAME_POLL slot=" + localSlot +
                " localPort=" + localPort +
                " src=" + packet.sourceSlot +
                " srcPort=" + packet.sourcePort +
                " bytes=" + packet.payload.length);
        }

        byte[] out = new byte[3 + packet.payload.length];
        out[0] = (byte)packet.sourceSlot;
        out[1] = (byte)((packet.sourcePort >>> 8) & 0xff);
        out[2] = (byte)(packet.sourcePort & 0xff);
        System.arraycopy(packet.payload, 0, out, 3, packet.payload.length);
        return out;
    }

    public boolean hasGameDatagram(int localPort) {
        ConcurrentLinkedQueue<GamePacket> queue = packetsByPort.get(localPort);
        return queue != null && queue.peek() != null;
    }

    public String pollNativeCommand() {
        String command = pendingNativeCommand.getAndSet("");
        return command == null ? "" : command;
    }

    private void queueNativeCommand(String command) {
        if (command == null || command.isEmpty()) return;
        pendingNativeCommand.updateAndGet(existing ->
            existing == null || existing.isEmpty() ? command : existing + command
        );
    }

    public void leaveRoom() {
        cancelMatchmaking();
        leaveGameRoomOnly();
        dismissTrackedDialog();
    }

    private void leaveGameRoomOnly() {
        gameSocketConnecting = false;
        WebSocket socket = gameSocket;
        gameSocket = null;
        if (socket != null) {
            try { socket.close(1000, "leave"); } catch (Exception ignored) {}
        }

        roomCode = "";
        localSlot = 0;
        targetPlayers = MAX_PLAYERS;
        matchStarted = false;
        hostPreparing = false;
        serverReadySent = false;
        serverReadyReceived = false;
        worldPhase = "lobby";
        worldRevision = 0;
        clientReadySent = false;
        ciReadySent = false;
        ciScenarioStarted = false;
        voiceChat.leaveRoom();
        connectedSlots.clear();
        packetsByPort.clear();
        gameTxTraceCount = 0;
        gameRxTraceCount = 0;
        gamePollTraceCount = 0;
        pendingNativeCommand.set("");
    }

    private void showMatchmakingSearchDialog() {
        activity.runOnUiThread(() -> {
            AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle("FIND MATCH - " + squadLabel(targetPlayers))
                .setMessage(
                    "SEARCHING...\n" +
                    prettyMap(selectedMap) + "\n" +
                    "PLAYERS 1/" + targetPlayers
                )
                .setNegativeButton("CANCEL SEARCH", (d, w) -> {
                    cancelMatchmaking();
                    showPublicSquadSizeMenu();
                })
                .create();
            dialog.setCancelable(false);
            dialog.setCanceledOnTouchOutside(false);
            matchmakingDialog = dialog;
            showTracked(dialog);
        });
    }

    private void updateMatchmakingStatus(int queued, int needed) {
        activity.runOnUiThread(() -> {
            AlertDialog dialog = matchmakingDialog;
            if (dialog == null || !dialog.isShowing()) return;
            dialog.setTitle("FIND MATCH - " + squadLabel(needed));
            dialog.setMessage(
                "SEARCHING...\n" +
                prettyMap(selectedMap) + "\n" +
                "PLAYERS " + Math.max(1, queued) + "/" + needed
            );
        });
    }

    private void updateMatchmakingReconnectState() {
        activity.runOnUiThread(() -> {
            AlertDialog dialog = matchmakingDialog;
            if (dialog == null || !dialog.isShowing()) return;
            dialog.setTitle("FIND MATCH - " + squadLabel(targetPlayers));
            dialog.setMessage(
                "RECONNECTING...\n" +
                prettyMap(selectedMap) + "\n" +
                "WAITING FOR NETWORK"
            );
        });
    }

    private void cancelMatchmaking() {
        matchmakingActive = false;
        WebSocket socket = matchSocket;
        matchSocket = null;
        matchmakingDialog = null;
        if (socket != null) {
            try { socket.close(1000, "cancel"); } catch (Exception ignored) {}
        }
    }

    public void shutdown() {
        leaveRoom();
        http.dispatcher().executorService().shutdown();
        http.connectionPool().evictAll();
    }

    private void showTracked(AlertDialog dialog) {
        dismissTrackedDialog();
        activeDialog = dialog;
        dialog.setOnDismissListener(d -> {
            if (activeDialog == dialog) activeDialog = null;
        });
        dialog.show();
    }

    private void dismissTrackedDialog() {
        activity.runOnUiThread(() -> {
            AlertDialog dialog = activeDialog;
            activeDialog = null;
            if (dialog != null && dialog.isShowing()) {
                try { dialog.dismiss(); } catch (Exception ignored) {}
            }
        });
    }

    private String websocketBase() {
        if (baseUrl.startsWith("https://")) {
            return "wss://" + baseUrl.substring(8);
        }
        if (baseUrl.startsWith("http://")) {
            return "ws://" + baseUrl.substring(7);
        }
        return baseUrl;
    }

    private static String prettyMap(String map) {
        return "ndu".equals(map) ? "Nacht der Untoten" : map;
    }

    private static String squadLabel(int players) {
        if (players == 2) return "DUO";
        if (players == 3) return "TRIO";
        return "QUAD";
    }

    private static String normalizeBaseUrl(String value) {
        if (value == null) return "";
        String out = value.trim();
        while (out.endsWith("/")) {
            out = out.substring(0, out.length() - 1);
        }
        return out;
    }

    private String loadPlayerId() {
        String saved = activity
            .getSharedPreferences("xziel_multiplayer", Context.MODE_PRIVATE)
            .getString("player_id", "");

        if (saved != null && !saved.isEmpty()) return saved;

        String androidId = Settings.Secure.getString(
            activity.getContentResolver(),
            Settings.Secure.ANDROID_ID
        );

        String generated =
            (androidId == null || androidId.isEmpty())
                ? UUID.randomUUID().toString()
                : "android-" + androidId;

        activity
            .getSharedPreferences("xziel_multiplayer", Context.MODE_PRIVATE)
            .edit()
            .putString("player_id", generated)
            .apply();

        return generated;
    }

    private void toast(String text) {
        activity.runOnUiThread(() ->
            Toast.makeText(activity, text, Toast.LENGTH_SHORT).show()
        );
    }
}
