package org.pyaudiogaming;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Application;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.DialogInterface;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.media.AudioManager;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.BaseInputConnection;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.InputMethodManager;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

public class PygameView extends View {
    public interface EventBridge {
        void onTouch(int action, int pointerId, float normX, float normY, int pxX, int pxY, int pointerCount);
        void onMultiGesture(float pinched, float rotated, float cx, float cy, int numFingers);
        void onKey(boolean isDown, int keyCode, int unicodeChar, int metaState);
        void onTextInput(String text);
        void onTextEditing(String text);
        void onFocusChanged(boolean focused);
        void onQuit();
    }

    private final Object frameLock = new Object();
    private Bitmap currentBitmap = null;
    private int logicalWidth = 800;
    private int logicalHeight = 600;
    private final Paint drawPaint = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Rect srcRect = new Rect();
    private final Rect dstRect = new Rect();
    private String overlayText = "Loading...";
    private boolean overlayIsError = false;

    private volatile EventBridge bridge = null;
    private volatile Activity hostActivity = null;
    private Application.ActivityLifecycleCallbacks lifecycleCallbacks = null;

    // Two-finger pinch / rotate tracking
    private boolean twoFingerActive = false;
    private float prevDist = 0f;
    private float prevAngle = 0f;

    public PygameView(Context context) {
        super(context);
        setFocusable(true);
        setFocusableInTouchMode(true);
        setKeepScreenOn(true);
        setBackgroundColor(Color.rgb(16, 18, 24));
    }

    public void setEventBridge(EventBridge bridge) {
        this.bridge = bridge;
    }

    public void setLogicalSize(int width, int height) {
        synchronized (frameLock) {
            this.logicalWidth = Math.max(1, width);
            this.logicalHeight = Math.max(1, height);
        }
    }

    public int getLogicalWidth() {
        synchronized (frameLock) {
            return logicalWidth;
        }
    }

    public int getLogicalHeight() {
        synchronized (frameLock) {
            return logicalHeight;
        }
    }

    public void presentBitmap(Bitmap bmp) {
        if (bmp == null) {
            return;
        }
        synchronized (frameLock) {
            if (currentBitmap == null
                    || currentBitmap.getWidth() != bmp.getWidth()
                    || currentBitmap.getHeight() != bmp.getHeight()) {
                currentBitmap = Bitmap.createBitmap(bmp.getWidth(), bmp.getHeight(), Bitmap.Config.ARGB_8888);
            }
            Canvas c = new Canvas(currentBitmap);
            c.drawBitmap(bmp, 0f, 0f, null);
        }
        postInvalidate();
    }

    public void setOverlayText(String text, boolean isError) {
        synchronized (frameLock) {
            this.overlayText = text == null ? "" : text;
            this.overlayIsError = isError;
        }
        postInvalidate();
    }

    public void showErrorDialog(final String title, final String message) {
        final String safeTitle = (title == null || title.isEmpty()) ? "Error" : title;
        final String safeMsg = (message == null) ? "" : message;
        setOverlayText(safeTitle + "\n" + safeMsg, true);
        final Activity act = this.hostActivity;
        if (act == null) {
            return;
        }
        act.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    float density = act.getResources().getDisplayMetrics().density;
                    int pad = (int) (16 * density);
                    ScrollView scroll = new ScrollView(act);
                    TextView tv = new TextView(act);
                    tv.setText(safeMsg);
                    tv.setTextIsSelectable(true);
                    tv.setTypeface(Typeface.MONOSPACE);
                    tv.setTextSize(12f);
                    tv.setPadding(pad, pad, pad, pad);
                    scroll.addView(tv);

                    AlertDialog.Builder builder = new AlertDialog.Builder(act);
                    builder.setTitle(safeTitle);
                    builder.setView(scroll);
                    builder.setCancelable(false);
                    builder.setNeutralButton("Copy", null);
                    builder.setPositiveButton("Close", new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface dialog, int which) {
                            dialog.dismiss();
                            closeApp();
                        }
                    });
                    final AlertDialog dlg = builder.create();
                    dlg.show();
                    if (dlg.getButton(AlertDialog.BUTTON_NEUTRAL) != null) {
                        dlg.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(new View.OnClickListener() {
                            @Override
                            public void onClick(View v) {
                                try {
                                    ClipboardManager cm = (ClipboardManager) act.getSystemService(Context.CLIPBOARD_SERVICE);
                                    if (cm != null) {
                                        cm.setPrimaryClip(ClipData.newPlainText(safeTitle, safeMsg));
                                        Toast.makeText(act, "Copied to clipboard", Toast.LENGTH_SHORT).show();
                                    }
                                } catch (Throwable ignored) {
                                }
                            }
                        });
                    }
                } catch (Throwable ignored) {
                }
            }
        });
    }

    public void attachToActivity(final Activity activity) {
        if (activity == null) {
            return;
        }
        this.hostActivity = activity;
        try {
            activity.setVolumeControlStream(AudioManager.STREAM_MUSIC);
        } catch (Throwable ignored) {
        }
        try {
            Window w = activity.getWindow();
            if (w != null) {
                w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            }
        } catch (Throwable ignored) {
        }
        activity.setContentView(
            this,
            new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        );
        requestFocus();

        Application app = activity.getApplication();
        if (app != null && lifecycleCallbacks == null) {
            lifecycleCallbacks = new Application.ActivityLifecycleCallbacks() {
                @Override
                public void onActivityCreated(Activity a, Bundle savedInstanceState) {}

                @Override
                public void onActivityStarted(Activity a) {}

                @Override
                public void onActivityResumed(Activity a) {
                    if (a == hostActivity && bridge != null) {
                        bridge.onFocusChanged(true);
                    }
                }

                @Override
                public void onActivityPaused(Activity a) {
                    if (a == hostActivity && bridge != null) {
                        bridge.onFocusChanged(false);
                    }
                }

                @Override
                public void onActivityStopped(Activity a) {}

                @Override
                public void onActivitySaveInstanceState(Activity a, Bundle outState) {}

                @Override
                public void onActivityDestroyed(Activity a) {
                    if (a == hostActivity && bridge != null) {
                        bridge.onQuit();
                    }
                }
            };
            app.registerActivityLifecycleCallbacks(lifecycleCallbacks);
        }
    }

    public void closeApp() {
        final Activity act = this.hostActivity;
        if (act != null) {
            act.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                            act.finishAndRemoveTask();
                        } else {
                            act.finishAffinity();
                        }
                    } catch (Throwable ignored) {
                        try {
                            act.finish();
                        } catch (Throwable ignored2) {
                        }
                    }
                    try {
                        android.os.Process.killProcess(android.os.Process.myPid());
                    } catch (Throwable ignored) {
                    }
                    System.exit(0);
                }
            });
        } else {
            try {
                android.os.Process.killProcess(android.os.Process.myPid());
            } catch (Throwable ignored) {
            }
            System.exit(0);
        }
    }

    public void showKeyboard() {
        post(new Runnable() {
            @Override
            public void run() {
                requestFocus();
                InputMethodManager imm = (InputMethodManager) getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
                if (imm != null) {
                    imm.showSoftInput(PygameView.this, InputMethodManager.SHOW_IMPLICIT);
                }
            }
        });
    }

    public void hideKeyboard() {
        post(new Runnable() {
            @Override
            public void run() {
                InputMethodManager imm = (InputMethodManager) getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
                if (imm != null) {
                    imm.hideSoftInputFromWindow(getWindowToken(), 0);
                }
            }
        });
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        canvas.drawColor(Color.rgb(16, 18, 24));
        Bitmap bmp;
        String ovText;
        boolean ovErr;
        synchronized (frameLock) {
            bmp = currentBitmap;
            ovText = overlayText;
            ovErr = overlayIsError;
        }
        if (bmp != null && !bmp.isRecycled() && !ovErr) {
            srcRect.set(0, 0, bmp.getWidth(), bmp.getHeight());
            dstRect.set(0, 0, getWidth(), getHeight());
            canvas.drawBitmap(bmp, srcRect, dstRect, drawPaint);
            return;
        }
        if (ovText != null && !ovText.isEmpty()) {
            float density = getResources().getDisplayMetrics().density;
            textPaint.setColor(ovErr ? Color.rgb(255, 110, 110) : Color.rgb(235, 240, 250));
            textPaint.setTextSize((ovErr ? 13f : 20f) * density);
            float pad = 18f * density;
            float maxW = Math.max(100f, getWidth() - pad * 2f);
            float lineH = textPaint.getFontSpacing();
            float y = pad + lineH;
            String[] rawLines = ovText.split("\n");
            for (String raw : rawLines) {
                int start = 0;
                int len = raw.length();
                if (len == 0) {
                    y += lineH;
                    continue;
                }
                while (start < len && y < getHeight() - pad) {
                    int count = textPaint.breakText(raw, start, len, true, maxW, null);
                    if (count <= 0) break;
                    canvas.drawText(raw, start, start + count, pad, y, textPaint);
                    start += count;
                    y += lineH;
                }
            }
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasWindowFocus) {
        super.onWindowFocusChanged(hasWindowFocus);
        EventBridge b = bridge;
        if (b != null) {
            b.onFocusChanged(hasWindowFocus);
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        EventBridge b = bridge;
        if (b == null) {
            return true;
        }
        int vw = Math.max(1, getWidth());
        int vh = Math.max(1, getHeight());
        int lw;
        int lh;
        synchronized (frameLock) {
            lw = logicalWidth;
            lh = logicalHeight;
        }

        int masked = event.getActionMasked();
        int count = event.getPointerCount();

        if (masked == MotionEvent.ACTION_DOWN || masked == MotionEvent.ACTION_POINTER_DOWN) {
            int idx = event.getActionIndex();
            int pid = event.getPointerId(idx);
            float nx = Math.max(0f, Math.min(1f, event.getX(idx) / vw));
            float ny = Math.max(0f, Math.min(1f, event.getY(idx) / vh));
            b.onTouch(0, pid, nx, ny, (int) (nx * lw), (int) (ny * lh), count);
            if (count == 2) {
                twoFingerActive = true;
                prevDist = calcDist(event, vw, vh);
                prevAngle = calcAngle(event);
            }
        } else if (masked == MotionEvent.ACTION_MOVE) {
            for (int i = 0; i < count; i++) {
                int pid = event.getPointerId(i);
                float nx = Math.max(0f, Math.min(1f, event.getX(i) / vw));
                float ny = Math.max(0f, Math.min(1f, event.getY(i) / vh));
                b.onTouch(1, pid, nx, ny, (int) (nx * lw), (int) (ny * lh), count);
            }
            if (count >= 2) {
                float dist = calcDist(event, vw, vh);
                float angle = calcAngle(event);
                if (twoFingerActive) {
                    float dPinch = dist - prevDist;
                    float dRot = angle - prevAngle;
                    if (dRot > Math.PI) dRot -= (float) (2.0 * Math.PI);
                    if (dRot < -Math.PI) dRot += (float) (2.0 * Math.PI);
                    if (Math.abs(dPinch) > 0.002f || Math.abs(dRot) > 0.01f) {
                        float cx = ((event.getX(0) + event.getX(1)) * 0.5f) / vw;
                        float cy = ((event.getY(0) + event.getY(1)) * 0.5f) / vh;
                        b.onMultiGesture(dPinch, dRot, cx, cy, count);
                    }
                }
                twoFingerActive = true;
                prevDist = dist;
                prevAngle = angle;
            }
        } else if (masked == MotionEvent.ACTION_UP || masked == MotionEvent.ACTION_POINTER_UP || masked == MotionEvent.ACTION_CANCEL) {
            if (masked == MotionEvent.ACTION_CANCEL) {
                for (int i = 0; i < count; i++) {
                    int pid = event.getPointerId(i);
                    float nx = Math.max(0f, Math.min(1f, event.getX(i) / vw));
                    float ny = Math.max(0f, Math.min(1f, event.getY(i) / vh));
                    b.onTouch(2, pid, nx, ny, (int) (nx * lw), (int) (ny * lh), 0);
                }
            } else {
                int idx = event.getActionIndex();
                int pid = event.getPointerId(idx);
                float nx = Math.max(0f, Math.min(1f, event.getX(idx) / vw));
                float ny = Math.max(0f, Math.min(1f, event.getY(idx) / vh));
                b.onTouch(2, pid, nx, ny, (int) (nx * lw), (int) (ny * lh), Math.max(0, count - 1));
            }
            if (count <= 2) {
                twoFingerActive = false;
            }
        }
        return true;
    }

    private float calcDist(MotionEvent e, int vw, int vh) {
        float dx = (e.getX(1) - e.getX(0)) / vw;
        float dy = (e.getY(1) - e.getY(0)) / vh;
        return (float) Math.sqrt(dx * dx + dy * dy);
    }

    private float calcAngle(MotionEvent e) {
        return (float) Math.atan2(e.getY(1) - e.getY(0), e.getX(1) - e.getX(0));
    }

    private boolean isSystemVolumeKey(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_VOLUME_UP
                || keyCode == KeyEvent.KEYCODE_VOLUME_DOWN
                || keyCode == KeyEvent.KEYCODE_VOLUME_MUTE;
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (isSystemVolumeKey(keyCode)) {
            return super.onKeyDown(keyCode, event);
        }
        EventBridge b = bridge;
        if (b != null) {
            int uni = event.getUnicodeChar();
            b.onKey(true, keyCode, uni, event.getMetaState());
            if (uni != 0 && !Character.isISOControl(uni)) {
                b.onTextInput(new String(Character.toChars(uni)));
            }
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public boolean onKeyUp(int keyCode, KeyEvent event) {
        if (isSystemVolumeKey(keyCode)) {
            return super.onKeyUp(keyCode, event);
        }
        EventBridge b = bridge;
        if (b != null) {
            b.onKey(false, keyCode, event.getUnicodeChar(), event.getMetaState());
            return true;
        }
        return super.onKeyUp(keyCode, event);
    }

    @Override
    public boolean onCheckIsTextEditor() {
        return true;
    }

    @Override
    public InputConnection onCreateInputConnection(EditorInfo outAttrs) {
        outAttrs.inputType = InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS;
        outAttrs.imeOptions = EditorInfo.IME_FLAG_NO_EXTRACT_UI | EditorInfo.IME_ACTION_DONE;
        return new BaseInputConnection(this, false) {
            @Override
            public boolean commitText(CharSequence text, int newCursorPosition) {
                EventBridge b = bridge;
                if (b != null && text != null && text.length() > 0) {
                    b.onTextInput(text.toString());
                }
                return true;
            }

            @Override
            public boolean setComposingText(CharSequence text, int newCursorPosition) {
                EventBridge b = bridge;
                if (b != null) {
                    b.onTextEditing(text == null ? "" : text.toString());
                }
                return true;
            }

            @Override
            public boolean deleteSurroundingText(int beforeLength, int afterLength) {
                EventBridge b = bridge;
                if (b != null && beforeLength > 0) {
                    for (int i = 0; i < beforeLength; i++) {
                        b.onKey(true, KeyEvent.KEYCODE_DEL, 0, 0);
                        b.onKey(false, KeyEvent.KEYCODE_DEL, 0, 0);
                    }
                    return true;
                }
                return super.deleteSurroundingText(beforeLength, afterLength);
            }

            @Override
            public boolean sendKeyEvent(KeyEvent event) {
                if (event.getAction() == KeyEvent.ACTION_DOWN) {
                    return onKeyDown(event.getKeyCode(), event);
                } else if (event.getAction() == KeyEvent.ACTION_UP) {
                    return onKeyUp(event.getKeyCode(), event);
                }
                return super.sendKeyEvent(event);
            }
        };
    }
}
