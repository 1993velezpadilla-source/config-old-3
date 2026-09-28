package com.pichy.ai;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.pichy.ai.local.LocalLlamaBridge;
import com.pichy.ai.local.LocalModelManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int REQ_ATTACH = 1001;
    private static final int MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    private LinearLayout transcript;
    private ScrollView scroll;
    private EditText prompt;
    private EditText endpoint;
    private EditText serverToken;
    private LinearLayout settingsPanel;
    private Button chatButton;
    private Button researchButton;
    private Button codeButton;
    private Button imageButton;
    private Button mapButton;
    private Button createButton;
    private Button attachButton;
    private Button localBrainButton;
    private Button localModeButton;
    private LinearLayout createMenu;
    private TextView status;
    private TextView attachmentStatus;

    private String sessionId;
    private String pendingAttachmentId = "";
    private String pendingAttachmentName = "";
    private LocalModelManager localModelManager;
    private LocalLlamaBridge localLlamaBridge;
    private boolean localModeEnabled = true;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sessionId = getPreferences(MODE_PRIVATE).getString("sessionId", "");
        if (sessionId.isEmpty()) {
            sessionId = UUID.randomUUID().toString().replace("-", "");
            getPreferences(MODE_PRIVATE).edit().putString("sessionId", sessionId).apply();
        }
        localModeEnabled = getPreferences(MODE_PRIVATE).getBoolean("localModeEnabled", true);
        localModelManager = new LocalModelManager(this);
        localLlamaBridge = new LocalLlamaBridge(this);

        getWindow().setStatusBarColor(Color.rgb(13, 13, 16));
        getWindow().setNavigationBarColor(Color.rgb(13, 13, 16));
        setContentView(buildUi());

        if (localModelManager.isInstalled()) {
            loadLocalBrain();
        } else {
            status.setText("LOCAL • install free brain in Settings");
        }
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(10), dp(12), dp(10));
        root.setBackgroundColor(Color.rgb(13, 13, 16));
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int left = insets.getSystemWindowInsetLeft();
            int top = insets.getSystemWindowInsetTop();
            int right = insets.getSystemWindowInsetRight();
            int bottom = insets.getSystemWindowInsetBottom();
            v.setPadding(dp(12) + left, dp(10) + top, dp(12) + right, dp(10) + bottom);
            return insets;
        });

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);

        TextView title = new TextView(this);
        title.setText("PICHY AI");
        title.setTextSize(24);
        title.setTextColor(Color.WHITE);
        title.setTypeface(null, 1);
        header.addView(title, new LinearLayout.LayoutParams(0, dp(48), 1));

        Button settings = makeButton("⚙");
        header.addView(settings, new LinearLayout.LayoutParams(dp(64), dp(48)));
        root.addView(header);

        status = new TextView(this);
        status.setText("LAB v0.5.0 • local-first • no paid API required");
        status.setTextColor(Color.rgb(155, 155, 170));
        status.setPadding(0, 0, 0, dp(6));
        root.addView(status);

        settingsPanel = buildSettings();
        settingsPanel.setVisibility(View.GONE);
        root.addView(settingsPanel);
        settings.setOnClickListener(v -> settingsPanel.setVisibility(
                settingsPanel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));

        scroll = new ScrollView(this);
        transcript = new LinearLayout(this);
        transcript.setOrientation(LinearLayout.VERTICAL);
        transcript.setPadding(0, dp(6), 0, dp(6));
        scroll.addView(transcript);
        root.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));

        LinearLayout composer = new LinearLayout(this);
        composer.setGravity(Gravity.BOTTOM);

        attachButton = makeButton("+");
        attachButton.setTextSize(24);
        composer.addView(attachButton, new LinearLayout.LayoutParams(dp(58), LinearLayout.LayoutParams.WRAP_CONTENT));

        prompt = new EditText(this);
        prompt.setHint("Ask Pichy anything...");
        prompt.setHintTextColor(Color.rgb(130, 130, 145));
        prompt.setTextColor(Color.WHITE);
        prompt.setBackgroundColor(Color.rgb(28, 28, 34));
        prompt.setPadding(dp(12), dp(10), dp(12), dp(10));
        prompt.setMinLines(2);
        prompt.setMaxLines(7);
        prompt.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        composer.addView(prompt, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        root.addView(composer);

        attachmentStatus = new TextView(this);
        attachmentStatus.setTextColor(Color.rgb(170, 200, 235));
        attachmentStatus.setPadding(dp(6), dp(3), dp(6), dp(3));
        attachmentStatus.setVisibility(View.GONE);
        root.addView(attachmentStatus);

        attachButton.setOnClickListener(v -> pickAttachment());

        createMenu = new LinearLayout(this);
        createMenu.setGravity(Gravity.CENTER);
        createMenu.setVisibility(View.GONE);
        imageButton = makeButton("Image");
        mapButton = makeButton("Map Modeling");
        createMenu.addView(imageButton, weight());
        createMenu.addView(mapButton, weight());
        root.addView(createMenu);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.CENTER);
        chatButton = makeButton("Chat");
        researchButton = makeButton("Research");
        codeButton = makeButton("Code");
        createButton = makeButton("Create");
        actions.addView(chatButton, weight());
        actions.addView(researchButton, weight());
        actions.addView(codeButton, weight());
        actions.addView(createButton, weight());
        root.addView(actions);

        chatButton.setOnClickListener(v -> {
            createMenu.setVisibility(View.GONE);
            sendChat("general");
        });
        researchButton.setOnClickListener(v -> {
            createMenu.setVisibility(View.GONE);
            sendChat("research");
        });
        codeButton.setOnClickListener(v -> {
            createMenu.setVisibility(View.GONE);
            sendChat("coding");
        });
        createButton.setOnClickListener(v -> createMenu.setVisibility(
                createMenu.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));
        imageButton.setOnClickListener(v -> {
            createMenu.setVisibility(View.GONE);
            sendImage(false);
        });
        mapButton.setOnClickListener(v -> {
            createMenu.setVisibility(View.GONE);
            sendChat("map_modeling");
        });

        addBubble("Pichy", "Ready. Chat, Research and Code stay on the main bar. Tap Create for Image or Map Modeling.");
        return root;
    }

    private LinearLayout buildSettings() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(0, 0, 0, dp(8));

        endpoint = new EditText(this);
        endpoint.setHint("Server URL");
        endpoint.setText(getPreferences(MODE_PRIVATE).getString(
                "endpoint",
                "https://pichy-ai-lab.onrender.com"));
        endpoint.setTextColor(Color.WHITE);
        endpoint.setHintTextColor(Color.GRAY);
        endpoint.setSingleLine(true);

        serverToken = new EditText(this);
        serverToken.setHint("Server token (optional)");
        serverToken.setText(getPreferences(MODE_PRIVATE).getString("serverToken", ""));
        serverToken.setTextColor(Color.WHITE);
        serverToken.setHintTextColor(Color.GRAY);
        serverToken.setSingleLine(true);
        serverToken.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);

        Button save = makeButton("Save settings");
        save.setOnClickListener(v -> {
            getPreferences(MODE_PRIVATE).edit()
                    .putString("endpoint", value(endpoint))
                    .putString("serverToken", value(serverToken))
                    .apply();
            Toast.makeText(this, "Saved", Toast.LENGTH_SHORT).show();
            checkHealth();
        });

        localModeButton = makeButton(localModeEnabled ? "Mode: Local (free)" : "Mode: Cloud (optional)");
        localModeButton.setOnClickListener(v -> {
            localModeEnabled = !localModeEnabled;
            getPreferences(MODE_PRIVATE).edit()
                    .putBoolean("localModeEnabled", localModeEnabled)
                    .apply();
            localModeButton.setText(localModeEnabled ? "Mode: Local (free)" : "Mode: Cloud (optional)");
            if (localModeEnabled) {
                if (localModelManager.isInstalled() && !localLlamaBridge.getReady()) {
                    loadLocalBrain();
                } else if (!localModelManager.isInstalled()) {
                    status.setText("LOCAL • model not installed");
                }
            } else {
                checkHealth();
            }
        });

        localBrainButton = makeButton(
                localModelManager.isInstalled()
                        ? "Load Local Brain • " + LocalModelManager.MODEL_NAME
                        : "Install Local Brain • 1.28 GB");
        localBrainButton.setOnClickListener(v -> installOrLoadLocalBrain());

        Button checkBrain = makeButton("Check brain");
        checkBrain.setOnClickListener(v -> checkBrain());

        Button newChat = makeButton("New conversation");
        newChat.setOnClickListener(v -> {
            sessionId = UUID.randomUUID().toString().replace("-", "");
            getPreferences(MODE_PRIVATE).edit().putString("sessionId", sessionId).apply();
            transcript.removeAllViews();
            clearPendingAttachment();
            addBubble("Pichy", "New conversation started.");
        });

        box.addView(localModeButton);
        box.addView(localBrainButton);
        box.addView(endpoint);
        box.addView(serverToken);
        box.addView(save);
        box.addView(checkBrain);
        box.addView(newChat);
        return box;
    }

    private void sendChat(String route) {
        String rawText = value(prompt);
        if (rawText.isEmpty() && pendingAttachmentId.isEmpty()) return;
        String text = rawText.isEmpty() ? "Analyze the attached file." : rawText;

        if (localModeEnabled) {
            sendLocalChat(route, text);
            return;
        }

        if (value(endpoint).isEmpty()) {
            Toast.makeText(this, "Set the server URL first.", Toast.LENGTH_SHORT).show();
            settingsPanel.setVisibility(View.VISIBLE);
            return;
        }
        prompt.setText("");
        String attachmentId = pendingAttachmentId;
        String attachmentName = pendingAttachmentName;
        addBubble("You", text + (attachmentName.isEmpty() ? "" : "\nAttached: " + attachmentName));
        setBusy(true, route);

        io.execute(() -> {
            try {
                JSONObject req = new JSONObject();
                req.put("session_id", sessionId);
                req.put("message", text);
                req.put("route", route);
                JSONArray attachmentIds = new JSONArray();
                if (!attachmentId.isEmpty()) attachmentIds.put(attachmentId);
                req.put("attachment_ids", attachmentIds);
                JSONObject out = postJson("/v1/chat", req);
                sessionId = out.optString("session_id", sessionId);
                String answer = out.optString("answer", "");
                runOnUiThread(() -> {
                    if (!attachmentId.isEmpty() && attachmentId.equals(pendingAttachmentId)) {
                        clearPendingAttachment();
                    }
                    addBubble("Pichy • " + route, answer);
                });
            } catch (Exception e) {
                runOnUiThread(() -> addBubble("Error", message(e)));
            } finally {
                runOnUiThread(() -> setBusy(false, ""));
            }
        });
    }

    private void sendImage(boolean newConcept) {
        String rawText = value(prompt);
        if (rawText.isEmpty() && pendingAttachmentId.isEmpty()) return;
        String text = rawText.isEmpty() ? "Use the attached image as the reference and create a refined version." : rawText;
        if (value(endpoint).isEmpty()) {
            Toast.makeText(this, "Set the server URL first.", Toast.LENGTH_SHORT).show();
            settingsPanel.setVisibility(View.VISIBLE);
            return;
        }
        prompt.setText("");
        String attachmentId = pendingAttachmentId;
        String attachmentName = pendingAttachmentName;
        addBubble("You • Image", text + (attachmentName.isEmpty() ? "" : "\nReference: " + attachmentName));
        setBusy(true, "image");

        io.execute(() -> {
            try {
                JSONObject req = new JSONObject();
                req.put("session_id", sessionId);
                req.put("prompt", text);
                req.put("new_concept", newConcept);
                req.put("size", "1024x1024");
                if (!attachmentId.isEmpty()) req.put("attachment_id", attachmentId);
                JSONObject out = postJson("/v1/image", req);
                sessionId = out.optString("session_id", sessionId);
                String effective = out.optString("effective_prompt", text);
                Bitmap bitmap = null;

                String b64 = out.optString("b64_json", "");
                String url = out.optString("url", "");
                if (!b64.isEmpty()) {
                    byte[] data = android.util.Base64.decode(b64, android.util.Base64.DEFAULT);
                    bitmap = BitmapFactory.decodeStream(new ByteArrayInputStream(data));
                } else if (!url.isEmpty()) {
                    bitmap = downloadBitmap(url);
                }

                boolean referenceApplied = out.optBoolean("reference_applied", false);
                Bitmap finalBitmap = bitmap;
                runOnUiThread(() -> {
                    if (!attachmentId.isEmpty() && attachmentId.equals(pendingAttachmentId)) {
                        clearPendingAttachment();
                    }
                    String referenceNote = referenceApplied
                            ? "Reference image applied at pixel level."
                            : "Prompt continuity applied; provider did not use an image-edit reference.";
                    addBubble("Pichy • Image", "Iteration ready. " + referenceNote + "\n\n" + effective);
                    if (finalBitmap != null) addImage(finalBitmap);
                });
            } catch (Exception e) {
                runOnUiThread(() -> addBubble("Error", message(e)));
            } finally {
                runOnUiThread(() -> setBusy(false, ""));
            }
        });
    }

    private void pickAttachment() {
        if (value(endpoint).isEmpty()) {
            Toast.makeText(this, "Set the server URL first.", Toast.LENGTH_SHORT).show();
            settingsPanel.setVisibility(View.VISIBLE);
            return;
        }
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, REQ_ATTACH);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_ATTACH && resultCode == RESULT_OK && data != null && data.getData() != null) {
            uploadAttachment(data.getData());
        }
    }

    private void uploadAttachment(Uri uri) {
        status.setText("Uploading attachment...");
        attachButton.setEnabled(false);
        io.execute(() -> {
            try {
                String mime = getContentResolver().getType(uri);
                if (mime == null || mime.isEmpty()) mime = "application/octet-stream";
                String name = attachmentDisplayName(uri);
                byte[] bytes = readAttachmentBytes(uri);
                String b64 = android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP);

                JSONObject req = new JSONObject();
                req.put("session_id", sessionId);
                req.put("filename", name);
                req.put("mime_type", mime);
                req.put("b64_data", b64);
                JSONObject out = postJson("/v1/attachments", req);

                String id = out.getString("attachment_id");
                String savedName = out.optString("filename", name);
                pendingAttachmentId = id;
                pendingAttachmentName = savedName;
                runOnUiThread(() -> {
                    attachmentStatus.setText("Attached • " + savedName);
                    attachmentStatus.setVisibility(View.VISIBLE);
                    status.setText("Ready • attachment loaded");
                    attachButton.setEnabled(true);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    attachButton.setEnabled(true);
                    status.setText("Attachment failed");
                    addBubble("Error", message(e));
                });
            }
        });
    }

    private String attachmentDisplayName(Uri uri) {
        String name = "attachment";
        try (Cursor c = getContentResolver().query(uri, null, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                int index = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) name = c.getString(index);
            }
        } catch (Exception ignored) {
        }
        return name == null || name.trim().isEmpty() ? "attachment" : name;
    }

    private byte[] readAttachmentBytes(Uri uri) throws Exception {
        try (InputStream in = getContentResolver().openInputStream(uri);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            if (in == null) throw new IllegalStateException("Unable to open attachment");
            byte[] buffer = new byte[8192];
            int total = 0;
            int n;
            while ((n = in.read(buffer)) != -1) {
                total += n;
                if (total > MAX_ATTACHMENT_BYTES) {
                    throw new IllegalArgumentException("Attachment is larger than 10 MB");
                }
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }

    private void clearPendingAttachment() {
        pendingAttachmentId = "";
        pendingAttachmentName = "";
        if (attachmentStatus != null) {
            attachmentStatus.setText("");
            attachmentStatus.setVisibility(View.GONE);
        }
    }

    private void installOrLoadLocalBrain() {
        if (localModelManager.isInstalled()) {
            loadLocalBrain();
            return;
        }

        localBrainButton.setEnabled(false);
        status.setText("LOCAL • downloading " + LocalModelManager.MODEL_NAME);
        localModelManager.download(new LocalModelManager.DownloadCallback() {
            @Override
            public void onProgress(long downloaded, long total) {
                int pct = total <= 0 ? 0 : (int) ((downloaded * 100L) / total);
                status.setText("LOCAL • downloading " + pct + "%");
                localBrainButton.setText("Downloading • " + pct + "%");
            }

            @Override
            public void onComplete(String path) {
                localBrainButton.setEnabled(true);
                localBrainButton.setText("Load Local Brain • " + LocalModelManager.MODEL_NAME);
                status.setText("LOCAL • verified • loading...");
                loadLocalBrain();
            }

            @Override
            public void onError(String message) {
                localBrainButton.setEnabled(true);
                localBrainButton.setText("Retry Local Brain • 1.28 GB");
                status.setText("LOCAL download failed");
                addBubble("Error", message);
            }
        });
    }

    private void loadLocalBrain() {
        if (!localModelManager.isInstalled()) {
            status.setText("LOCAL • model not installed");
            return;
        }

        status.setText("LOCAL • loading " + LocalModelManager.MODEL_NAME + "...");
        if (localBrainButton != null) localBrainButton.setEnabled(false);

        String systemPrompt =
                "You are Pichy AI running fully on-device. Be useful, direct, multilingual, and honest. "
                        + "Do not claim to have internet or tools unless context was explicitly supplied. "
                        + "For coding, give executable engineering help. For map modeling, think in production "
                        + "game-level terms: scale, zones, traversal, lighting, collision, navmesh, streaming, "
                        + "optimization and asset manifests. Do not output private chain-of-thought.";

        localLlamaBridge.load(
                localModelManager.getModelFile().getAbsolutePath(),
                systemPrompt,
                new LocalLlamaBridge.Callback() {
                    @Override
                    public void onReady() {
                        if (localBrainButton != null) {
                            localBrainButton.setEnabled(true);
                            localBrainButton.setText("Local Brain Ready • " + LocalModelManager.MODEL_NAME);
                        }
                        status.setText("LOCAL READY • " + LocalModelManager.MODEL_NAME);
                    }

                    @Override
                    public void onComplete(String text) {
                    }

                    @Override
                    public void onError(String message) {
                        if (localBrainButton != null) localBrainButton.setEnabled(true);
                        status.setText("LOCAL load failed");
                        addBubble("Error", message);
                    }
                });
    }

    private void sendLocalChat(String route, String text) {
        if (!pendingAttachmentId.isEmpty()) {
            Toast.makeText(
                    this,
                    "Local attachment analysis is the next step. Clear the attachment or switch to optional cloud mode.",
                    Toast.LENGTH_LONG).show();
            return;
        }

        if (!localModelManager.isInstalled()) {
            settingsPanel.setVisibility(View.VISIBLE);
            status.setText("LOCAL • install the free model first");
            Toast.makeText(this, "Install Local Brain in Settings first.", Toast.LENGTH_LONG).show();
            return;
        }

        if (!localLlamaBridge.getReady()) {
            loadLocalBrain();
            Toast.makeText(this, "Local brain is loading. Try again when it says LOCAL READY.", Toast.LENGTH_LONG).show();
            return;
        }

        prompt.setText("");
        addBubble("You", text);
        setBusy(true, "local " + route);

        String routed = localRoutePrompt(route, text);
        localLlamaBridge.generate(routed, 768, new LocalLlamaBridge.Callback() {
            @Override
            public void onReady() {
            }

            @Override
            public void onComplete(String answer) {
                addBubble("Pichy • LOCAL • " + route, answer);
                setBusy(false, "");
            }

            @Override
            public void onError(String message) {
                addBubble("Error", message);
                setBusy(false, "");
            }
        });
    }

    private String localRoutePrompt(String route, String text) {
        switch (route) {
            case "coding":
                return "[CODING MODE] Inspect the problem carefully. Give concrete code/commands and validation steps.\n\n" + text;
            case "research":
                return "[RESEARCH MODE] Analyze carefully. You are offline unless sources are included, so clearly separate known background from anything that would require current web verification.\n\n" + text;
            case "map_modeling":
                return "[MAP MODELING MODE] Produce a production-oriented 3D game map plan. Cover scale, zones, connectivity, traversal, combat spaces, lighting, collision, navmesh, streaming, LOD/occlusion, props and asset manifest. Use stable IDs when useful.\n\n" + text;
            default:
                return text;
        }
    }

    private void checkHealth() {
        String base = value(endpoint);
        if (base.isEmpty()) return;
        io.execute(() -> {
            try {
                HttpURLConnection c = open("/health", "GET");
                String body = read(c);
                int responseCode = c.getResponseCode();
                if (responseCode >= 200 && responseCode < 300) {
                    JSONObject out = new JSONObject(body);
                    runOnUiThread(() -> status.setText("Connected • Pichy " + out.optString("version", "?")));
                } else {
                    runOnUiThread(() -> status.setText("Server error " + responseCode));
                }
            } catch (Exception e) {
                runOnUiThread(() -> status.setText("Offline • " + message(e)));
            }
        });
    }

    private void checkBrain() {
        if (localModeEnabled) {
            String installed = localModelManager.isInstalled() ? "installed" : "not installed";
            String ready = localLlamaBridge.getReady() ? "ready" : "not loaded";
            status.setText("LOCAL • " + installed + " • " + ready);
            addBubble("Pichy • Brain Check",
                    "Local model: " + LocalModelManager.MODEL_NAME + "\n"
                            + "Model file: " + installed + "\n"
                            + "Inference engine: " + ready + "\n"
                            + "API key required: no");
            return;
        }

        if (value(endpoint).isEmpty()) {
            Toast.makeText(this, "Set the server URL first.", Toast.LENGTH_SHORT).show();
            return;
        }
        status.setText("Checking brain...");
        io.execute(() -> {
            try {
                HttpURLConnection c = open("/v1/provider-status", "GET");
                String body = read(c);
                int responseCode = c.getResponseCode();
                if (responseCode < 200 || responseCode >= 300) {
                    throw new IllegalStateException("HTTP " + responseCode + ": " + body);
                }
                JSONObject out = new JSONObject(body);
                JSONObject models = out.optJSONObject("models");
                int total = 0;
                int ready = 0;
                if (models != null) {
                    java.util.Iterator<String> keys = models.keys();
                    while (keys.hasNext()) {
                        String key = keys.next();
                        total++;
                        JSONObject item = models.optJSONObject(key);
                        if (item != null && item.optBoolean("key_present", false)) ready++;
                    }
                }
                JSONObject image = out.optJSONObject("image");
                boolean imageReady = image != null && image.optBoolean("key_present", false);
                int finalReady = ready;
                int finalTotal = total;
                runOnUiThread(() -> {
                    status.setText("Brain • " + finalReady + "/" + finalTotal + " model routes ready");
                    addBubble("Pichy • Brain Check",
                            finalReady + " of " + finalTotal + " configured model profiles have credentials. "
                                    + "Image provider: " + (imageReady ? "ready" : "not ready") + ".");
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    status.setText("Brain check failed");
                    addBubble("Error", message(e));
                });
            }
        });
    }

    private JSONObject postJson(String path, JSONObject body) throws Exception {
        HttpURLConnection c = open(path, "POST");
        c.setRequestProperty("Content-Type", "application/json");
        c.setDoOutput(true);
        try (OutputStream os = c.getOutputStream()) {
            os.write(body.toString().getBytes(StandardCharsets.UTF_8));
        }
        String text = read(c);
        if (c.getResponseCode() < 200 || c.getResponseCode() >= 300) {
            throw new IllegalStateException("HTTP " + c.getResponseCode() + ": " + text);
        }
        return new JSONObject(text);
    }

    private HttpURLConnection open(String path, String method) throws Exception {
        String base = value(endpoint);
        while (base.endsWith("/")) base = base.substring(0, base.length() - 1);
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(20000);
        c.setReadTimeout(300000);
        String token = value(serverToken);
        if (!token.isEmpty()) c.setRequestProperty("X-Pichy-Token", token);
        return c;
    }

    private String read(HttpURLConnection c) throws Exception {
        InputStream stream = c.getResponseCode() >= 400 ? c.getErrorStream() : c.getInputStream();
        if (stream == null) return "";
        try (BufferedReader br = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = br.readLine()) != null) sb.append(line).append('\n');
            return sb.toString();
        }
    }

    private Bitmap downloadBitmap(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(20000);
        c.setReadTimeout(180000);
        try (InputStream in = c.getInputStream()) {
            return BitmapFactory.decodeStream(in);
        }
    }

    private void addBubble(String who, String text) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(12), dp(10), dp(12), dp(10));
        card.setBackgroundColor(who.startsWith("You") ? Color.rgb(47, 35, 65) : Color.rgb(28, 28, 34));

        TextView head = new TextView(this);
        head.setText(who);
        head.setTextColor(who.startsWith("You") ? Color.rgb(225, 188, 255) : Color.rgb(180, 220, 255));
        head.setTypeface(null, 1);
        card.addView(head);

        TextView body = new TextView(this);
        body.setText(text);
        body.setTextSize(16);
        body.setTextColor(Color.WHITE);
        body.setTextIsSelectable(true);
        card.addView(body);

        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, dp(4), 0, dp(4));
        transcript.addView(card, p);
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private void addImage(Bitmap bitmap) {
        ImageView iv = new ImageView(this);
        iv.setAdjustViewBounds(true);
        iv.setImageBitmap(bitmap);
        iv.setPadding(0, dp(6), 0, dp(12));
        transcript.addView(iv, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private Button makeButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        return b;
    }

    private LinearLayout.LayoutParams weight() {
        return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
    }

    private String value(EditText e) {
        return e.getText().toString().trim();
    }

    private void setBusy(boolean busy, String mode) {
        prompt.setEnabled(!busy);
        chatButton.setEnabled(!busy);
        researchButton.setEnabled(!busy);
        codeButton.setEnabled(!busy);
        imageButton.setEnabled(!busy);
        mapButton.setEnabled(!busy);
        createButton.setEnabled(!busy);
        attachButton.setEnabled(!busy);
        if (busy) createMenu.setVisibility(View.GONE);
        if (busy) {
            status.setText("Working • " + mode);
        } else if (localModeEnabled && localLlamaBridge.getReady()) {
            status.setText("LOCAL READY • " + LocalModelManager.MODEL_NAME);
        } else {
            status.setText("Ready • session " + sessionId.substring(0, 8));
        }
    }

    private String message(Exception e) {
        String m = e.getMessage();
        return m == null ? e.getClass().getSimpleName() : m;
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        if (localModelManager != null) localModelManager.close();
        if (localLlamaBridge != null) localLlamaBridge.close();
        super.onDestroy();
    }
}
