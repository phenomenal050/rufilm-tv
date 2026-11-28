package tv.rufilm.app

import android.app.Activity
import android.content.pm.ActivityInfo
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import android.webkit.CookieManager
import android.webkit.WebSettings
import io.github.yuroyami.libmpv.MpvCommand
import io.github.yuroyami.libmpv.view.MpvOptions
import io.github.yuroyami.libmpv.view.MpvView
import org.json.JSONObject
import java.util.HashMap
import java.util.Locale

class NativePlayerActivity : Activity() {
    companion object {
        const val EXTRA_URL = "media_url"
        const val EXTRA_AUDIO_URL = "media_audio_url"
        const val EXTRA_REFERER = "media_referer"
        const val EXTRA_USER_AGENT = "media_user_agent"
        const val EXTRA_HEADERS = "media_headers"
        const val EXTRA_EPISODE_SELECTORS = "episode_selectors"
        const val EXTRA_START_POSITION_MS = "start_position_ms"
    }

    private val handler = Handler(Looper.getMainLooper())
    private lateinit var mpvView: MpvView
    private lateinit var currentText: TextView
    private lateinit var durationText: TextView
    private lateinit var seekBar: SeekBar
    private lateinit var playButton: TextView
    private var currentUrl = ""
    private var currentAudioUrl: String? = null
    private var referer = ""
    private var userAgent = ""
    private var headers = HashMap<String, String>()
    private var baseline = 0L
    private var requestedPosition = 0L
    private var startPositionApplied = false
    private var released = false
    private var controlsVisible = true
    private var volume = 100.0

    private val ticker = object : Runnable {
        override fun run() {
            if (released) return
            try {
                val position = mpvView.timePos ?: 0.0
                val duration = mpvView.duration ?: 0.0
                currentText.text = formatTime((position * 1000).toLong())
                durationText.text = formatTime((duration * 1000).toLong())
                if (duration > 0 && !seekBar.isPressed) {
                    seekBar.progress = (position / duration * 1000.0).toInt().coerceIn(0, 1000)
                }
                playButton.text = if (mpvView.paused) "▶" else "Ⅱ"
                if (!startPositionApplied && requestedPosition > 0 && position >= 0.0) {
                    startPositionApplied = true
                    mpvView.timePos = requestedPosition / 1000.0
                }
                MainActivity.syncOriginalPlayback((position * 1000).toLong(), true)
            } catch (_: Exception) { }
            handler.postDelayed(this, 500)
        }
    }

    private val episodePoll = object : Runnable {
        override fun run() {
            if (released || isFinishing) return
            try {
                val snapshot = JSONObject(MainActivity.getCapturedMediaSnapshot())
                val capturedAt = snapshot.optLong("capturedAt", 0L)
                val next = snapshot.optString("url", "")
                if (capturedAt > baseline && next.isNotBlank() && next != currentUrl) {
                    val nextHeaders = HashMap<String, String>()
                    val jsonHeaders = snapshot.optJSONObject("headers")
                    if (jsonHeaders != null) {
                        val keys = jsonHeaders.keys()
                        while (keys.hasNext()) {
                            val key = keys.next()
                            nextHeaders[key] = jsonHeaders.optString(key, "")
                        }
                    }
                    val nextReferer = snapshot.optString("referer", referer)
                    val nextUa = snapshot.optString("userAgent", userAgent)
                    nextHeaders["Referer"] = nextReferer
                    nextHeaders["User-Agent"] = nextUa
                    val audio = snapshot.optString("audioUrl", "").takeIf { it.isNotBlank() }
                    openStream(next, audio, nextHeaders, nextReferer, nextUa, 0L)
                    baseline = capturedAt
                }
            } catch (_: Exception) { }
            handler.postDelayed(this, 900)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = android.graphics.Color.BLACK
        window.navigationBarColor = android.graphics.Color.BLACK
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE

        currentUrl = intent.getStringExtra(EXTRA_URL).orEmpty()
        currentAudioUrl = intent.getStringExtra(EXTRA_AUDIO_URL)
        referer = intent.getStringExtra(EXTRA_REFERER).orEmpty()
        userAgent = intent.getStringExtra(EXTRA_USER_AGENT).orEmpty()
        requestedPosition = intent.getLongExtra(EXTRA_START_POSITION_MS, 0L).coerceAtLeast(0L)
        if (!currentUrl.startsWith("http://") && !currentUrl.startsWith("https://")) {
            Toast.makeText(this, "Не удалось получить прямую ссылку на видео", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        try {
            @Suppress("DEPRECATION")
            val supplied = intent.getSerializableExtra(EXTRA_HEADERS)
            if (supplied is Map<*, *>) {
                supplied.forEach { (key, value) ->
                    if (key is String && value is String) headers[key] = value
                }
            }
        } catch (_: Exception) { }
        if (userAgent.isBlank()) userAgent = WebSettings.getDefaultUserAgent(this)
        headers["User-Agent"] = userAgent
        if (referer.isNotBlank()) headers["Referer"] = referer
        try {
            val cookie = CookieManager.getInstance().getCookie(currentUrl)
            if (!cookie.isNullOrBlank() && headers.keys.none { it.equals("Cookie", true) }) headers["Cookie"] = cookie
        } catch (_: Exception) { }

        buildUi()
        try {
            mpvView.initialize(MpvOptions(extra = mapOf(
                "network-caching" to "1800",
                "demuxer-max-bytes" to "67108864",
                "demuxer-max-back-bytes" to "16777216",
                "hwdec" to "auto",
                "keep-open" to "yes"
            )))
            baseline = MainActivity.getCapturedMediaAt()
            openStream(currentUrl, currentAudioUrl, headers, referer, userAgent, requestedPosition)
            handler.post(ticker)
            handler.postDelayed(episodePoll, 1000)
        } catch (e: Exception) {
            android.util.Log.e("RuFilmTV-MPV", "MPV initialization failed", e)
            Toast.makeText(this, "Не удалось запустить MPV: ${e.javaClass.simpleName}", Toast.LENGTH_LONG).show()
            finish()
        }
    }

    private fun buildUi() {
        val root = FrameLayout(this).apply { setBackgroundColor(android.graphics.Color.BLACK) }
        mpvView = MpvView(this)
        root.addView(mpvView, FrameLayout.LayoutParams(-1, -1))

        val overlay = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(8), dp(18), dp(10))
            setBackgroundColor(0x55000000)
        }
        val top = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        val title = controlText("RUFILM TV · MPV", 16)
        top.addView(title, LinearLayout.LayoutParams(0, dp(44), 1f))
        val exit = controlText("Выход", 14)
        top.addView(exit, LinearLayout.LayoutParams(dp(76), dp(44)))
        exit.setOnClickListener { finish() }
        overlay.addView(top)

        val timeline = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        currentText = controlText("0:00", 12)
        durationText = controlText("0:00", 12)
        seekBar = SeekBar(this).apply { max = 1000; isFocusable = true }
        timeline.addView(currentText, LinearLayout.LayoutParams(dp(54), dp(34)))
        timeline.addView(seekBar, LinearLayout.LayoutParams(0, dp(34), 1f))
        timeline.addView(durationText, LinearLayout.LayoutParams(dp(54), dp(34)))
        overlay.addView(timeline)
        seekBar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(bar: SeekBar, value: Int, fromUser: Boolean) {
                if (fromUser) {
                    val duration = mpvView.duration ?: 0.0
                    currentText.text = formatTime((duration * value / 1000.0 * 1000).toLong())
                }
            }
            override fun onStartTrackingTouch(bar: SeekBar) = Unit
            override fun onStopTrackingTouch(bar: SeekBar) {
                val duration = mpvView.duration ?: 0.0
                if (duration > 0) mpvView.timePos = duration * bar.progress / 1000.0
            }
        })

        val controls = LinearLayout(this).apply { gravity = Gravity.CENTER }
        val back = controlText("↶10", 18)
        controls.addView(back, LinearLayout.LayoutParams(dp(70), dp(52)))
        back.setOnClickListener { seekBy(-10.0) }
        playButton = controlText("▶", 26)
        controls.addView(playButton, LinearLayout.LayoutParams(dp(76), dp(52)))
        playButton.setOnClickListener { mpvView.paused = !mpvView.paused }
        val forward = controlText("10↷", 18)
        controls.addView(forward, LinearLayout.LayoutParams(dp(70), dp(52)))
        forward.setOnClickListener { seekBy(10.0) }
        val vol = controlText("🔊", 18)
        controls.addView(vol, LinearLayout.LayoutParams(dp(62), dp(52)))
        vol.setOnClickListener {
            volume = if (volume > 0.0) 0.0 else 100.0
            mpvView.volume = volume
            vol.text = if (volume == 0.0) "🔇" else "🔊"
        }
        overlay.addView(controls)
        val params = FrameLayout.LayoutParams(-1, dp(142), Gravity.BOTTOM)
        root.addView(overlay, params)
        overlay.setOnClickListener { showControls() }
        mpvView.setOnClickListener { toggleControls() }
        setContentView(root)
    }

    private fun openStream(url: String, audioUrl: String?, requestHeaders: Map<String, String>, pageReferer: String, ua: String, startMs: Long) {
        val isSocial = (url + " " + pageReferer).lowercase(Locale.ROOT).let {
            it.contains("ok.ru") || it.contains("vk.com") || it.contains("vk.ru") || it.contains("vkvideo")
        }
        val videoPlayback = if (isSocial || audioUrl != null) LocalStreamProxy.start(url, requestHeaders) else url
        currentUrl = url
        currentAudioUrl = audioUrl
        referer = pageReferer
        userAgent = ua
        headers = HashMap(requestHeaders)
        mpvView.playFile(videoPlayback)
        if (!audioUrl.isNullOrBlank()) {
            val audioPlayback = LocalStreamProxy.start(audioUrl, requestHeaders)
            handler.postDelayed({
                if (!released) {
                    try { mpvView.mpv?.command(MpvCommand.of("audio-add", audioPlayback, "select")) }
                    catch (e: Exception) { android.util.Log.w("RuFilmTV-MPV", "Separate audio track attach failed", e) }
                }
            }, 700)
        }
        if (startMs > 0) {
            handler.postDelayed({ if (!released) mpvView.timePos = startMs / 1000.0 }, 1200)
        }
        android.util.Log.i("RuFilmTV-MPV", "MPV stream opened social=$isSocial")
    }

    private fun seekBy(seconds: Double) {
        val duration = mpvView.duration ?: 0.0
        val target = ((mpvView.timePos ?: 0.0) + seconds).coerceAtLeast(0.0)
        mpvView.timePos = if (duration > 0) target.coerceAtMost(duration) else target
    }

    private fun showControls() {
        controlsVisible = true
        handler.removeCallbacks(hideControls)
        handler.postDelayed(hideControls, 6000)
    }
    private val hideControls = Runnable {
        controlsVisible = false
        if (::mpvView.isInitialized && !released) {
            // Keep the video view untouched; the control layer is toggled by its parent.
            (mpvView.parent as? FrameLayout)?.getChildAt(1)?.visibility = View.GONE
        }
    }
    private fun toggleControls() {
        controlsVisible = !controlsVisible
        if (::mpvView.isInitialized) (mpvView.parent as? FrameLayout)?.getChildAt(1)?.visibility =
            if (controlsVisible) View.VISIBLE else View.GONE
        if (controlsVisible) showControls()
    }
    private fun controlText(value: String, size: Int) = TextView(this).apply {
        text = value
        textSize = size.toFloat()
        setTextColor(android.graphics.Color.WHITE)
        gravity = Gravity.CENTER
        isFocusable = true
    }
    private fun formatTime(ms: Long): String {
        val total = (ms / 1000).coerceAtLeast(0)
        val h = total / 3600
        val m = (total % 3600) / 60
        val s = total % 60
        return if (h > 0) String.format(Locale.ROOT, "%d:%02d:%02d", h, m, s)
            else String.format(Locale.ROOT, "%d:%02d", m, s)
    }
    private fun dp(value: Int) = (value * resources.displayMetrics.density + 0.5f).toInt()

    override fun onStop() {
        releasePlayer()
        super.onStop()
    }
    override fun onDestroy() {
        releasePlayer()
        super.onDestroy()
    }
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        releasePlayer()
        super.onBackPressed()
    }
    private fun releasePlayer() {
        if (released) return
        released = true
        handler.removeCallbacks(ticker)
        handler.removeCallbacks(episodePoll)
        handler.removeCallbacks(hideControls)
        try {
            if (::mpvView.isInitialized) {
                val pos = ((mpvView.timePos ?: 0.0) * 1000).toLong()
                MainActivity.syncOriginalPlayback(pos, false)
                mpvView.destroy()
            }
        } catch (e: Exception) {
            android.util.Log.w("RuFilmTV-MPV", "MPV release warning", e)
        }
    }
}
