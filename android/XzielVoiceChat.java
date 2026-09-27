package org.libsdl.app;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioRecord;
import android.media.AudioTrack;
import android.media.MediaRecorder;
import android.media.audiofx.AcousticEchoCanceler;
import android.media.audiofx.AutomaticGainControl;
import android.media.audiofx.NoiseSuppressor;
import android.os.Build;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import okio.ByteString;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * Xziel room voice chat.
 *
 * Voice v1 uses bounded PCM16 16 kHz mono frames over the room Durable Object.
 * Every frame carries the sender's authoritative game slot plus current player
 * position. Receivers apply local distance attenuation, so gameplay remains
 * server-authoritative while voice proximity is presentation-only.
 */
public final class XzielVoiceChat {
    public static final int MIC_PERMISSION_REQUEST = 7741;

    private static final String TAG = "XzielVoice";
    private static final int SAMPLE_RATE = 16000;
    private static final int FRAME_SAMPLES = 320; // 20 ms
    private static final int FRAME_BYTES = FRAME_SAMPLES * 2;
    private static final int HEADER_BYTES = 24;
    private static final int FLAG_POSITION_VALID = 1;
    private static final int FLAG_CI_TONE = 2;

    // Quake units. Full voice nearby, smooth falloff, silent beyond max.
    private static final float PROX_FULL_DISTANCE = 220.0f;
    private static final float PROX_MAX_DISTANCE = 1200.0f;

    private final Activity activity;
    private final OkHttpClient http;
    private final Runnable ciEvidenceDoneCallback;
    private final ConcurrentHashMap<Integer, AudioTrack> remoteTracks =
        new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, Boolean> playerMuted =
        new ConcurrentHashMap<>();
    private final Set<Integer> connectedPlayers = ConcurrentHashMap.newKeySet();

    private final AtomicBoolean micMuted = new AtomicBoolean(false);
    private final AtomicBoolean speakerMuted = new AtomicBoolean(false);
    private final AtomicInteger sequence = new AtomicInteger();

    private volatile String baseUrl = "";
    private volatile String roomCode = "";
    private volatile String playerId = "";
    private volatile int localSlot;
    private volatile WebSocket voiceSocket;

    private volatile float localX;
    private volatile float localY;
    private volatile float localZ;
    private volatile boolean localPositionValid;

    private volatile AudioRecord recorder;
    private volatile Thread captureThread;
    private volatile boolean captureRunning;

    private volatile LinearLayout hudOverlay;
    private volatile VoiceIconView micButton;
    private volatile VoiceIconView speakerButton;
    private volatile LinearLayout pausePanel;

    private AcousticEchoCanceler echoCanceler;
    private NoiseSuppressor noiseSuppressor;
    private AutomaticGainControl automaticGainControl;

    public XzielVoiceChat(Activity activity, OkHttpClient http,
                          Runnable ciEvidenceDoneCallback) {
        this.activity = activity;
        this.http = http;
        this.ciEvidenceDoneCallback = ciEvidenceDoneCallback;
    }

    public void connect(String endpoint, String code, String id, int slot) {
        leaveRoom();

        baseUrl = normalizeBaseUrl(endpoint);
        roomCode = code == null ? "" : code;
        playerId = id == null ? "" : id;
        localSlot = slot;
        connectedPlayers.add(slot);

        if (baseUrl.isEmpty() || roomCode.isEmpty() || localSlot < 1) return;

        openVoiceSocket();
    }

    private void openVoiceSocket() {
        if (baseUrl.isEmpty() || roomCode.isEmpty() || localSlot < 1 ||
            voiceSocket != null) {
            return;
        }

        final String expectedRoom = roomCode;
        final int expectedSlot = localSlot;
        String wsUrl = websocketBase() + "/voice/" + expectedRoom +
            "?playerId=" + playerId;
        Request request = new Request.Builder().url(wsUrl).build();

        voiceSocket = http.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket webSocket, Response response) {
                if (!expectedRoom.equals(roomCode) || expectedSlot != localSlot) {
                    try { webSocket.close(1000, "stale"); } catch (Exception ignored) {}
                    return;
                }
                Log.i(TAG, "VOICE_OPEN slot=" + localSlot + " room=" + roomCode);
                showHudControls();
                if (!micMuted.get()) startCaptureIfPermitted();
            }

            @Override
            public void onMessage(WebSocket webSocket, ByteString bytes) {
                if (voiceSocket == webSocket) {
                    handleVoicePacket(bytes.toByteArray());
                }
            }

            @Override
            public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                if (voiceSocket == webSocket) voiceSocket = null;
                stopCapture();
                Log.w(TAG, "VOICE_FAILURE slot=" + expectedSlot, t);
                scheduleReconnect(expectedRoom, expectedSlot);
            }

            @Override
            public void onClosed(WebSocket webSocket, int code, String reason) {
                if (voiceSocket == webSocket) voiceSocket = null;
                stopCapture();
                Log.i(TAG, "VOICE_CLOSED slot=" + expectedSlot + " reason=" + reason);
                scheduleReconnect(expectedRoom, expectedSlot);
            }
        });
    }

    private void scheduleReconnect(String expectedRoom, int expectedSlot) {
        activity.getWindow().getDecorView().postDelayed(() -> {
            if (voiceSocket == null &&
                expectedRoom.equals(roomCode) &&
                expectedSlot == localSlot &&
                localSlot >= 1) {
                Log.i(TAG, "VOICE_RECONNECT slot=" + localSlot);
                openVoiceSocket();
            }
        }, 1500);
    }

    public void setPlayerConnected(int slot, boolean connected) {
        if (slot < 1 || slot > 4) return;
        if (connected) {
            connectedPlayers.add(slot);
        } else {
            connectedPlayers.remove(slot);
            playerMuted.remove(slot);
            AudioTrack track = remoteTracks.remove(slot);
            releaseTrack(track);
        }
        refreshPausePanel();
    }

    public void updateLocalPosition(float x, float y, float z) {
        localX = x;
        localY = y;
        localZ = z;
        localPositionValid = true;
    }

    public boolean isMicMuted() {
        return micMuted.get();
    }

    public boolean isSpeakerMuted() {
        return speakerMuted.get();
    }

    public boolean isPlayerMuted(int slot) {
        return Boolean.TRUE.equals(playerMuted.get(slot));
    }

    public void toggleMic() {
        boolean muted = !micMuted.get();
        micMuted.set(muted);
        if (muted) {
            stopCapture();
        } else {
            startCaptureIfPermitted();
        }
        refreshHudControls();
        refreshPausePanel();
        toast(muted ? "MIC MUTED" : "MIC ON");
        Log.i(TAG, "MIC_MUTED=" + muted);
    }

    public void toggleSpeaker() {
        boolean muted = !speakerMuted.get();
        speakerMuted.set(muted);
        for (java.util.Map.Entry<Integer, AudioTrack> entry : remoteTracks.entrySet()) {
            try {
                boolean playerIsMuted = isPlayerMuted(entry.getKey());
                entry.getValue().setVolume(
                    muted || playerIsMuted ? 0.0f : 1.0f
                );
            } catch (Exception ignored) {}
        }
        refreshHudControls();
        refreshPausePanel();
        toast(muted ? "VOICE AUDIO MUTED" : "VOICE AUDIO ON");
        Log.i(TAG, "SPEAKER_MUTED=" + muted);
    }

    public void togglePlayerMute(int slot) {
        if (slot < 1 || slot > 4 || slot == localSlot) return;
        boolean muted = !isPlayerMuted(slot);
        if (muted) playerMuted.put(slot, true);
        else playerMuted.remove(slot);

        AudioTrack track = remoteTracks.get(slot);
        if (track != null) {
            try { track.setVolume(muted || speakerMuted.get() ? 0.0f : 1.0f); }
            catch (Exception ignored) {}
        }

        refreshPausePanel();
        toast("PLAYER " + slot + (muted ? " MUTED" : " UNMUTED"));
        Log.i(TAG, "PLAYER_MUTE slot=" + slot + " muted=" + muted);

        // CI completion is tied to the last real evidence interaction: a
        // successful per-player mute. Normal gameplay gets a no-op callback.
        if (muted && ciEvidenceDoneCallback != null) {
            ciEvidenceDoneCallback.run();
        }
    }

    public void sendCiTestTone() {
        WebSocket socket = voiceSocket;
        if (socket == null || localSlot < 1) {
            Log.w(TAG, "CI_TONE_SKIPPED slot=" + localSlot + " socket=false");
            return;
        }

        byte[] pcm = new byte[FRAME_BYTES];
        ByteBuffer samples = ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN);
        double phaseBase = localSlot * 0.31;
        for (int i = 0; i < FRAME_SAMPLES; i++) {
            double t = (double)i / (double)SAMPLE_RATE;
            short sample = (short)(Math.sin(
                2.0 * Math.PI * (420.0 + localSlot * 55.0) * t + phaseBase
            ) * 9000.0);
            samples.putShort(sample);
        }

        int sent = 0;
        for (int frame = 0; frame < 10; frame++) {
            if (socket.send(ByteString.of(buildVoicePacket(pcm, FLAG_CI_TONE)))) {
                sent++;
            }
        }

        Log.i(TAG, "CI_TONE_SENT slot=" + localSlot +
            " frames=" + sent +
            " pos=" + localX + "," + localY + "," + localZ);
    }

    public void onMicrophonePermissionResult(boolean granted) {
        if (granted && !micMuted.get()) {
            startCaptureIfPermitted();
        } else if (!granted) {
            micMuted.set(true);
            refreshHudControls();
            refreshPausePanel();
            toast("Microphone permission denied - voice transmit muted");
        }
    }

    public void showHudControls() {
        activity.runOnUiThread(() -> {
            if (hudOverlay != null || roomCode.isEmpty()) {
                refreshHudControls();
                return;
            }

            LinearLayout row = new LinearLayout(activity);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER);
            row.setPadding(dp(4), dp(4), dp(4), dp(4));
            row.setBackgroundColor(0x66000000);

            micButton = new VoiceIconView(activity, VoiceIconView.TYPE_MIC);
            speakerButton = new VoiceIconView(activity, VoiceIconView.TYPE_SPEAKER);

            micButton.setContentDescription("Mute microphone");
            speakerButton.setContentDescription("Mute voice audio");
            micButton.setOnClickListener(v -> toggleMic());
            speakerButton.setOnClickListener(v -> toggleSpeaker());

            int size = dp(38);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(size, size);
            lp.setMargins(dp(2), 0, dp(2), 0);
            row.addView(micButton, lp);
            row.addView(speakerButton, lp);

            FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            );
            params.gravity = Gravity.TOP | Gravity.START;
            params.topMargin = dp(12);
            params.leftMargin = dp(12);

            activity.addContentView(row, params);
            hudOverlay = row;
            refreshHudControls();
        });
    }

    public void showPausePanel() {
        activity.runOnUiThread(() -> {
            if (roomCode.isEmpty()) return;
            if (pausePanel == null) {
                LinearLayout panel = new LinearLayout(activity);
                panel.setOrientation(LinearLayout.VERTICAL);
                panel.setPadding(dp(10), dp(8), dp(10), dp(8));
                panel.setBackgroundColor(0xCC0E1116);

                FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                    dp(190), ViewGroup.LayoutParams.WRAP_CONTENT
                );
                params.gravity = Gravity.CENTER_VERTICAL | Gravity.END;
                params.rightMargin = dp(18);
                activity.addContentView(panel, params);
                pausePanel = panel;
            }
            rebuildPausePanel();
        });
    }

    public void hidePausePanel() {
        activity.runOnUiThread(() -> {
            LinearLayout panel = pausePanel;
            pausePanel = null;
            if (panel != null && panel.getParent() instanceof ViewGroup) {
                ((ViewGroup) panel.getParent()).removeView(panel);
            }
        });
    }

    private void rebuildPausePanel() {
        LinearLayout panel = pausePanel;
        if (panel == null) return;
        panel.removeAllViews();

        TextView title = new TextView(activity);
        title.setText("VOICE");
        title.setTextColor(0xFFFFEB3B);
        title.setTextSize(15);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER);
        panel.addView(title, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        for (int slot = 1; slot <= 4; slot++) {
            if (!connectedPlayers.contains(slot)) continue;

            LinearLayout row = new LinearLayout(activity);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, dp(3), 0, dp(3));

            TextView label = new TextView(activity);
            label.setText(slot == localSlot ? "YOU  •  P" + slot : "PLAYER " + slot);
            label.setTextColor(Color.WHITE);
            label.setTextSize(13);
            row.addView(label, new LinearLayout.LayoutParams(
                0, dp(38), 1.0f));

            VoiceIconView icon = new VoiceIconView(
                activity,
                slot == localSlot ? VoiceIconView.TYPE_MIC : VoiceIconView.TYPE_SPEAKER
            );
            icon.setMuted(slot == localSlot ? micMuted.get() : isPlayerMuted(slot));
            if (slot == localSlot) {
                icon.setContentDescription(micMuted.get()
                    ? "Unmute microphone" : "Mute microphone");
                icon.setOnClickListener(v -> toggleMic());
            } else {
                final int playerSlot = slot;
                icon.setContentDescription(
                    (isPlayerMuted(slot) ? "Unmute Player " : "Mute Player ") + slot
                );
                icon.setOnClickListener(v -> togglePlayerMute(playerSlot));
            }
            row.addView(icon, new LinearLayout.LayoutParams(dp(36), dp(36)));
            panel.addView(row, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        }

        TextView global = new TextView(activity);
        global.setText(speakerMuted.get() ? "ALL VOICE: MUTED" : "PROXIMITY VOICE: ON");
        global.setTextColor(speakerMuted.get() ? 0xFFFF5252 : 0xFF8BE28B);
        global.setTextSize(11);
        global.setGravity(Gravity.CENTER);
        global.setPadding(0, dp(4), 0, 0);
        global.setOnClickListener(v -> toggleSpeaker());
        panel.addView(global, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private void refreshPausePanel() {
        activity.runOnUiThread(this::rebuildPausePanel);
    }

    private void refreshHudControls() {
        activity.runOnUiThread(() -> {
            if (micButton != null) {
                micButton.setMuted(micMuted.get());
                micButton.setContentDescription(micMuted.get()
                    ? "Unmute microphone" : "Mute microphone");
            }
            if (speakerButton != null) {
                speakerButton.setMuted(speakerMuted.get());
                speakerButton.setContentDescription(speakerMuted.get()
                    ? "Unmute voice audio" : "Mute voice audio");
            }
        });
    }

    private void hideHudControls() {
        activity.runOnUiThread(() -> {
            LinearLayout row = hudOverlay;
            hudOverlay = null;
            micButton = null;
            speakerButton = null;
            if (row != null && row.getParent() instanceof ViewGroup) {
                ((ViewGroup) row.getParent()).removeView(row);
            }
        });
    }

    private void startCaptureIfPermitted() {
        if (voiceSocket == null || micMuted.get() || captureRunning) return;

        if (Build.VERSION.SDK_INT >= 23 &&
            activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            activity.runOnUiThread(() ->
                activity.requestPermissions(
                    new String[] { Manifest.permission.RECORD_AUDIO },
                    MIC_PERMISSION_REQUEST
                ));
            return;
        }

        int minBuffer = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT);
        if (minBuffer <= 0) minBuffer = FRAME_BYTES * 8;
        int bufferSize = Math.max(minBuffer, FRAME_BYTES * 8);

        AudioRecord record;
        try {
            record = new AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize
            );
        } catch (Exception e) {
            micMuted.set(true);
            refreshHudControls();
            toast("Could not open microphone");
            return;
        }

        if (record.getState() != AudioRecord.STATE_INITIALIZED) {
            record.release();
            micMuted.set(true);
            refreshHudControls();
            toast("Microphone initialization failed");
            return;
        }

        recorder = record;
        enableVoiceEffects(record.getAudioSessionId());
        captureRunning = true;

        try {
            record.startRecording();
        } catch (Exception e) {
            captureRunning = false;
            recorder = null;
            record.release();
            micMuted.set(true);
            refreshHudControls();
            return;
        }

        captureThread = new Thread(() -> {
            byte[] pcm = new byte[FRAME_BYTES];

            while (captureRunning && recorder == record) {
                int offset = 0;
                while (offset < pcm.length && captureRunning) {
                    int read = record.read(pcm, offset, pcm.length - offset);
                    if (read <= 0) {
                        offset = 0;
                        break;
                    }
                    offset += read;
                }

                if (offset != pcm.length || micMuted.get()) continue;

                WebSocket socket = voiceSocket;
                if (socket != null) {
                    socket.send(ByteString.of(buildVoicePacket(pcm, 0)));
                }
            }
        }, "XzielVoiceCapture");
        captureThread.setDaemon(true);
        captureThread.start();
        Log.i(TAG, "CAPTURE_STARTED slot=" + localSlot);
    }

    private byte[] buildVoicePacket(byte[] pcm, int extraFlags) {
        ByteBuffer packet = ByteBuffer.allocate(HEADER_BYTES + pcm.length)
            .order(ByteOrder.LITTLE_ENDIAN);
        packet.put((byte)'X');
        packet.put((byte)'V');
        packet.put((byte)'C');
        packet.put((byte)'1');
        packet.put((byte)localSlot);
        int flags = extraFlags | (localPositionValid ? FLAG_POSITION_VALID : 0);
        packet.put((byte)flags);
        packet.putShort((short)0);
        packet.putInt(sequence.incrementAndGet());
        packet.putFloat(localX);
        packet.putFloat(localY);
        packet.putFloat(localZ);
        packet.put(pcm);
        return packet.array();
    }

    private void handleVoicePacket(byte[] data) {
        if (speakerMuted.get() || data == null || data.length <= HEADER_BYTES) return;

        ByteBuffer packet = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        if (packet.get() != 'X' || packet.get() != 'V' ||
            packet.get() != 'C' || packet.get() != '1') return;

        int senderSlot = packet.get() & 0xff;
        int flags = packet.get() & 0xff;
        packet.getShort();
        packet.getInt();
        float senderX = packet.getFloat();
        float senderY = packet.getFloat();
        float senderZ = packet.getFloat();

        if (senderSlot < 1 || senderSlot > 4 || senderSlot == localSlot) return;
        if (isPlayerMuted(senderSlot)) return;

        float volume = 1.0f;
        float distance = 0.0f;
        boolean senderPositionValid = (flags & FLAG_POSITION_VALID) != 0;
        if (localPositionValid && senderPositionValid) {
            float dx = senderX - localX;
            float dy = senderY - localY;
            float dz = senderZ - localZ;
            distance = (float)Math.sqrt(dx * dx + dy * dy + dz * dz);
            volume = proximityGain(distance);
            if (volume <= 0.001f) {
                if ((flags & FLAG_CI_TONE) != 0) {
                    Log.i(TAG, "CI_VOICE_OUT_OF_RANGE receiver=" + localSlot +
                        " sender=" + senderSlot + " distance=" + distance);
                }
                return;
            }
        }

        byte[] pcm = new byte[packet.remaining()];
        packet.get(pcm);
        if (pcm.length != FRAME_BYTES) return;

        AudioTrack track = remoteTracks.computeIfAbsent(
            senderSlot, this::createPlaybackTrack);
        if (track == null) return;

        try {
            track.setVolume(volume);
            int written = track.write(
                pcm, 0, pcm.length, AudioTrack.WRITE_NON_BLOCKING);

            if ((flags & FLAG_CI_TONE) != 0) {
                ByteBuffer sampleBuffer = ByteBuffer.wrap(pcm)
                    .order(ByteOrder.LITTLE_ENDIAN);
                double energy = 0.0;
                int count = 0;
                while (sampleBuffer.remaining() >= 2) {
                    short sample = sampleBuffer.getShort();
                    energy += (double)sample * (double)sample;
                    count++;
                }
                double rms = count > 0 ? Math.sqrt(energy / count) : 0.0;
                Log.i(TAG, "CI_VOICE_PLAY receiver=" + localSlot +
                    " sender=" + senderSlot +
                    " bytes=" + written +
                    " distance=" + distance +
                    " gain=" + volume +
                    " rms=" + rms);
            }
        } catch (Exception e) {
            if ((flags & FLAG_CI_TONE) != 0) {
                Log.w(TAG, "CI_VOICE_PLAY_FAILED receiver=" + localSlot +
                    " sender=" + senderSlot, e);
            }
        }
    }

    private float proximityGain(float distance) {
        if (distance <= PROX_FULL_DISTANCE) return 1.0f;
        if (distance >= PROX_MAX_DISTANCE) return 0.0f;
        float t = (distance - PROX_FULL_DISTANCE) /
            (PROX_MAX_DISTANCE - PROX_FULL_DISTANCE);
        float gain = 1.0f - t;
        return gain * gain;
    }

    private AudioTrack createPlaybackTrack(int slot) {
        try {
            int minBuffer = AudioTrack.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT);
            if (minBuffer <= 0) minBuffer = FRAME_BYTES * 8;

            AudioAttributes attributes = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build();

            AudioFormat format = new AudioFormat.Builder()
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setSampleRate(SAMPLE_RATE)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .build();

            AudioTrack track = new AudioTrack(
                attributes,
                format,
                Math.max(minBuffer, FRAME_BYTES * 8),
                AudioTrack.MODE_STREAM,
                AudioManager.AUDIO_SESSION_ID_GENERATE
            );
            track.play();
            Log.i(TAG, "PLAYBACK_TRACK slot=" + slot);
            return track;
        } catch (Exception e) {
            Log.w(TAG, "Could not create playback track slot=" + slot, e);
            return null;
        }
    }

    private void stopCapture() {
        captureRunning = false;
        AudioRecord record = recorder;
        recorder = null;

        if (record != null) {
            try { record.stop(); } catch (Exception ignored) {}
            try { record.release(); } catch (Exception ignored) {}
        }

        Thread thread = captureThread;
        captureThread = null;
        if (thread != null && thread != Thread.currentThread()) {
            try { thread.join(250); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }
        releaseVoiceEffects();
    }

    private void enableVoiceEffects(int sessionId) {
        try {
            if (AcousticEchoCanceler.isAvailable()) {
                echoCanceler = AcousticEchoCanceler.create(sessionId);
                if (echoCanceler != null) echoCanceler.setEnabled(true);
            }
        } catch (Exception ignored) {}

        try {
            if (NoiseSuppressor.isAvailable()) {
                noiseSuppressor = NoiseSuppressor.create(sessionId);
                if (noiseSuppressor != null) noiseSuppressor.setEnabled(true);
            }
        } catch (Exception ignored) {}

        try {
            if (AutomaticGainControl.isAvailable()) {
                automaticGainControl = AutomaticGainControl.create(sessionId);
                if (automaticGainControl != null) automaticGainControl.setEnabled(true);
            }
        } catch (Exception ignored) {}
    }

    private void releaseVoiceEffects() {
        try { if (echoCanceler != null) echoCanceler.release(); } catch (Exception ignored) {}
        try { if (noiseSuppressor != null) noiseSuppressor.release(); } catch (Exception ignored) {}
        try { if (automaticGainControl != null) automaticGainControl.release(); } catch (Exception ignored) {}
        echoCanceler = null;
        noiseSuppressor = null;
        automaticGainControl = null;
    }

    public void leaveRoom() {
        // Clear room identity before closing so onClosed cannot schedule a
        // reconnect for an intentionally-left room.
        roomCode = "";
        playerId = "";
        localSlot = 0;
        localPositionValid = false;

        stopCapture();

        WebSocket socket = voiceSocket;
        voiceSocket = null;
        if (socket != null) {
            try { socket.close(1000, "leave"); } catch (Exception ignored) {}
        }

        for (AudioTrack track : remoteTracks.values()) releaseTrack(track);
        remoteTracks.clear();
        connectedPlayers.clear();
        playerMuted.clear();

        hidePausePanel();
        hideHudControls();
    }

    private void releaseTrack(AudioTrack track) {
        if (track == null) return;
        try { track.pause(); } catch (Exception ignored) {}
        try { track.flush(); } catch (Exception ignored) {}
        try { track.release(); } catch (Exception ignored) {}
    }

    private String websocketBase() {
        if (baseUrl.startsWith("https://")) return "wss://" + baseUrl.substring(8);
        if (baseUrl.startsWith("http://")) return "ws://" + baseUrl.substring(7);
        return baseUrl;
    }

    private static String normalizeBaseUrl(String value) {
        if (value == null) return "";
        String out = value.trim();
        while (out.endsWith("/")) out = out.substring(0, out.length() - 1);
        return out;
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    private void toast(String message) {
        activity.runOnUiThread(() ->
            Toast.makeText(activity, message, Toast.LENGTH_SHORT).show());
    }

    private static final class VoiceIconView extends View {
        static final int TYPE_MIC = 1;
        static final int TYPE_SPEAKER = 2;

        private final int type;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path path = new Path();
        private boolean muted;

        VoiceIconView(Context context, int type) {
            super(context);
            this.type = type;
            setClickable(true);
            setFocusable(true);
        }

        void setMuted(boolean value) {
            muted = value;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float w = getWidth();
            float h = getHeight();
            float cx = w * 0.5f;
            float cy = h * 0.5f;
            float r = Math.min(w, h) * 0.42f;

            paint.setStyle(Paint.Style.FILL);
            paint.setColor(0xDD11151B);
            canvas.drawCircle(cx, cy, r, paint);

            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(Math.max(2.0f, r * 0.10f));
            paint.setColor(0xFFF2EA2A);
            canvas.drawCircle(cx, cy, r, paint);

            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeJoin(Paint.Join.ROUND);
            paint.setColor(Color.WHITE);
            paint.setStrokeWidth(Math.max(2.0f, r * 0.12f));

            if (type == TYPE_MIC) drawMic(canvas, cx, cy, r);
            else drawSpeaker(canvas, cx, cy, r);

            if (muted) {
                paint.setColor(0xFFFF5252);
                paint.setStrokeWidth(Math.max(3.0f, r * 0.14f));
                canvas.drawLine(cx - r * 0.62f, cy - r * 0.62f,
                    cx + r * 0.62f, cy + r * 0.62f, paint);
            }
        }

        private void drawMic(Canvas canvas, float cx, float cy, float r) {
            paint.setStyle(Paint.Style.STROKE);
            RectF capsule = new RectF(
                cx - r * 0.23f, cy - r * 0.55f,
                cx + r * 0.23f, cy + r * 0.20f);
            canvas.drawRoundRect(capsule, r * 0.23f, r * 0.23f, paint);
            canvas.drawArc(
                cx - r * 0.42f, cy - r * 0.13f,
                cx + r * 0.42f, cy + r * 0.48f,
                0, 180, false, paint);
            canvas.drawLine(cx, cy + r * 0.48f, cx, cy + r * 0.68f, paint);
            canvas.drawLine(cx - r * 0.24f, cy + r * 0.68f,
                cx + r * 0.24f, cy + r * 0.68f, paint);
        }

        private void drawSpeaker(Canvas canvas, float cx, float cy, float r) {
            paint.setStyle(Paint.Style.STROKE);
            path.reset();
            path.moveTo(cx - r * 0.52f, cy - r * 0.18f);
            path.lineTo(cx - r * 0.25f, cy - r * 0.18f);
            path.lineTo(cx + r * 0.02f, cy - r * 0.43f);
            path.lineTo(cx + r * 0.02f, cy + r * 0.43f);
            path.lineTo(cx - r * 0.25f, cy + r * 0.18f);
            path.lineTo(cx - r * 0.52f, cy + r * 0.18f);
            path.close();
            canvas.drawPath(path, paint);
            canvas.drawArc(
                cx - r * 0.05f, cy - r * 0.36f,
                cx + r * 0.50f, cy + r * 0.36f,
                -55, 110, false, paint);
            canvas.drawArc(
                cx - r * 0.03f, cy - r * 0.56f,
                cx + r * 0.72f, cy + r * 0.56f,
                -55, 110, false, paint);
        }
    }
}
