package com.driveflow.monitor

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.Icon
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.WindowInsets
import android.widget.*
import com.google.android.gms.tasks.Task
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.google.firebase.FirebaseApp
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.*
import java.security.MessageDigest
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : Activity() {
    private val auth by lazy { FirebaseAuth.getInstance() }
    private val db by lazy { FirebaseFirestore.getInstance() }
    private val prefs by lazy { getSharedPreferences("monitor", MODE_PRIVATE) }
    private val states = linkedMapOf<String, DocumentSnapshot?>()
    private val names = mutableMapOf<String, String>()
    private val subscriptions = mutableMapOf<String, ListenerRegistration>()
    private var membership: ListenerRegistration? = null
    private var selected: String? = null
    private var settingsTab = false
    private var renderedPage = ""
    private var message = "Conectando…"
    private var ready = false
    private var pairing = false
    private var foreground = false
    private lateinit var root: LinearLayout
    private lateinit var content: LinearLayout
    private val handler = Handler(Looper.getMainLooper())
    private val refreshAge = object : Runnable {
        override fun run() { render(); handler.postDelayed(this, 15000) }
    }
    private val themes = linkedMapOf(
        "Azul profundo" to listOf("#0c1420", "#111d2c", "#2b3c51", "#66d7b0"),
        "Cinza grafite" to listOf("#141619", "#1b1e23", "#383f49", "#98baff"),
        "Verde escuro" to listOf("#0c1916", "#11231e", "#2a473c", "#84d6aa"),
        "Spotify" to listOf("#121212", "#181818", "#363636", "#1DB954"))
    private fun color(index: Int) = Color.parseColor((themes[prefs.getString("theme", "Azul profundo")] ?: themes.values.first())[index])
    private val ink = Color.parseColor("#e4eaf2")
    private val muted = Color.parseColor("#91a3b7")
    private fun dp(n: Int) = (n * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        selected = savedInstanceState?.getString("selected") ?: intent.getStringExtra("computer_id")
        settingsTab = savedInstanceState?.getBoolean("settingsTab") ?: false
        render()
    }
    override fun onStart() { super.onStart(); foreground = true; connect() }
    override fun onStop() {
        foreground = false
        membership?.remove(); membership = null
        subscriptions.values.forEach { it.remove() }; subscriptions.clear()
        ready = false
        super.onStop()
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        selected = intent.getStringExtra("computer_id")
        settingsTab = false
        render()
    }
    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("selected", selected)
        outState.putBoolean("settingsTab", settingsTab)
        super.onSaveInstanceState(outState)
    }
    override fun onResume() {
        super.onResume()
        handler.postDelayed(refreshAge, 15000)
        window.decorView.post {
            if (foreground && !prefs.getBoolean("homeShortcutRequested", false)) requestHomeShortcut(false)
        }
    }
    override fun onPause() { handler.removeCallbacks(refreshAge); super.onPause() }
    override fun onDestroy() {
        membership?.remove(); subscriptions.values.forEach { it.remove() }
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun connect() {
        message = "Conectando…"; render()
        if (auth.currentUser != null) listen()
        else auth.signInAnonymously().addOnSuccessListener { if (!isDestroyed && foreground) listen() }
            .addOnFailureListener { fail("Não foi possível conectar. Verifique a internet e se o acesso anônimo está ativado no Firebase.") }
    }
    private fun listen() {
        if (!foreground) return
        val uid = auth.currentUser?.uid ?: return
        membership?.remove()
        membership = db.collection("readers").document(uid).collection("computers")
            .addSnapshotListener(MetadataChanges.INCLUDE) { snapshot, error ->
                if (isDestroyed || !foreground) return@addSnapshotListener
                if (error != null) { fail("Não foi possível ler seus vínculos. Verifique a conexão e a configuração do serviço."); return@addSnapshotListener }
                if (snapshot == null) return@addSnapshotListener
                ready = true
                message = if (snapshot.metadata.isFromCache) "Sem confirmação do servidor • dados salvos" else "Seus computadores, em tempo real"
                val ids = snapshot.documents.map { it.id }.toSet()
                states.keys.toList().filter { it !in ids }.forEach {
                    subscriptions.remove(it)?.remove(); states.remove(it); names.remove(it)
                }
                snapshot.documents.forEach { link ->
                    names[link.id] = link.getString("computer_name") ?: link.id
                    if (link.id !in subscriptions) {
                        states[link.id] = null
                        subscriptions[link.id] = db.collection("computers").document(link.id)
                            .addSnapshotListener(MetadataChanges.INCLUDE) { doc, err ->
                                if (!isDestroyed && foreground) {
                                    states[link.id] = if (err == null) doc else null
                                    if (err != null) message = "Um computador está indisponível ou teve o acesso revogado."
                                    render()
                                }
                            }
                    }
                }
                render()
            }
    }

    private fun shape(fill: Int, stroke: Boolean = false) = GradientDrawable().apply {
        setColor(fill); cornerRadius = dp(16).toFloat()
        if (stroke) setStroke(dp(1), color(2))
    }
    private fun text(value: String, size: Float = 15f, tint: Int = ink, bold: Boolean = false) = TextView(this).apply {
        text = value; textSize = size; setTextColor(tint)
        if (bold) setTypeface(null, Typeface.BOLD)
        setPadding(0, dp(5), 0, dp(5))
    }
    private fun action(title: String, primary: Boolean = false, block: () -> Unit) = Button(this).apply {
        text = title; isAllCaps = false; textSize = 14f; minHeight = dp(48)
        setTextColor(if (primary) Color.parseColor("#0c211c") else ink)
        background = shape(color(if (primary) 3 else 1), !primary)
        setPadding(dp(16), dp(10), dp(16), dp(10))
        setOnClickListener { block() }
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) }
    }
    private fun panel() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(16), dp(20), dp(16))
        background = shape(color(1), true)
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(16) }
    }
    private fun render() {
        if (isDestroyed) return
        val page = if (settingsTab) "settings" else if (selected != null && selected in names) "details:$selected" else "home"
        val scrollPosition = if (::root.isInitialized && page == renderedPage) (root.getChildAt(1) as? ScrollView)?.scrollY ?: 0 else 0
        renderedPage = page
        root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(color(0)) }
        root.setOnApplyWindowInsetsListener { v, insets ->
            if (Build.VERSION.SDK_INT >= 30) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars())
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            } else v.setPadding(0, insets.systemWindowInsetTop, 0, insets.systemWindowInsetBottom)
            insets
        }
        val header = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), dp(12), dp(24), dp(12)) }
        header.addView(ImageView(this).apply {
            setImageResource(R.drawable.logo)
            contentDescription = "Datarestore — Recuperação de dados"
            scaleType = ImageView.ScaleType.FIT_CENTER
        }, LinearLayout.LayoutParams(-1, dp(60)))
        root.addView(header)
        val scroll = ScrollView(this).apply { isFillViewport = true }
        content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), 0, dp(24), dp(28)) }
        scroll.addView(content)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(navigation())
        setContentView(root)
        if (settingsTab) settingsPage() else if (selected != null && selected in names) details(selected!!) else listPage()
        scroll.post { scroll.scrollTo(0, scrollPosition) }
    }
    private fun listPage() {
        val brand = LinearLayout(this).apply {
            gravity = Gravity.CENTER; orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(4), 0, dp(8))
        }
        brand.addView(ImageView(this).apply {
            setImageResource(R.drawable.ic_upload)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }, LinearLayout.LayoutParams(dp(32), dp(32)).apply { marginEnd = dp(10) })
        brand.addView(text("Drive Flow", 28f, color(3), true))
        // Balance the icon so the text itself is centered on the screen.
        brand.addView(Space(this), LinearLayout.LayoutParams(dp(42), dp(1)))
        content.addView(brand)
        content.addView(text("MONITOR • ANDROID", 11f, muted).apply { gravity = Gravity.CENTER })
        content.addView(text("Seus computadores", 25f, ink, true))
        content.addView(text(message, 13f, muted))
        content.addView(action(if (pairing) "Conectando computador…" else "+  Escanear QR code", true) { if (!pairing) scan() }.apply { isEnabled = ready && !pairing })
        if (states.isEmpty()) {
            content.addView(panel().apply {
                addView(text("Tudo em um só lugar", 20f, ink, true))
                addView(text("No DriveFlow do Windows, abra Configurações → Conectar celular. Escaneie o QR code para acompanhar os uploads desta máquina.", 15f, muted))
                addView(text("Você pode adicionar mais de um computador.", 13f, color(3)))
            })
        }
        states.forEach { (id, doc) ->
            content.addView(panel().apply {
                addView(text(names[id] ?: id, 20f, ink, true))
                statusLine(this, doc)
                if (doc?.exists() == true) {
                    addView(text(doc.getString("current_file")?.ifBlank { "Nenhum arquivo em envio" } ?: "Nenhum arquivo em envio", 14f, muted))
                    progress(this, doc)
                    addView(text("${doc.getLong("queue_remaining") ?: 0} restantes  •  ${MonitorModel.bytes(number(doc, "upload_speed"))}/s", 13f, muted))
                }
                addView(action("Ver detalhes") { selected = id; render() })
            })
        }
    }
    private fun navigation(): LinearLayout {
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(16), dp(8), dp(16), dp(8))
            setBackgroundColor(color(1))
        }
        fun tab(label: String, icon: Int, active: Boolean, tintIcon: Boolean, click: () -> Unit) {
            val item = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER
                setPadding(dp(8), dp(8), dp(8), dp(8))
                background = shape(color(if (active) 2 else 1))
                isClickable = true; isFocusable = true; isSelected = active
                contentDescription = label
                setOnClickListener { click() }
            }
            item.addView(ImageView(this).apply {
                setImageResource(icon)
                if (tintIcon) imageTintList = ColorStateList.valueOf(if (active) color(3) else muted)
                importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            }, LinearLayout.LayoutParams(dp(24), dp(24)))
            item.addView(text(label, 12f, if (active) color(3) else muted, active).apply {
                gravity = Gravity.CENTER
                textAlignment = View.TEXT_ALIGNMENT_CENTER
                importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            }, LinearLayout.LayoutParams(-1, -2))
            bar.addView(item, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(4); marginEnd = dp(4) })
        }
        tab("Computadores", R.drawable.ic_upload, !settingsTab, false) { settingsTab = false; selected = null; render() }
        tab("Configurações", R.drawable.ic_settings, settingsTab, true) { settingsTab = true; render() }
        return bar
    }
    private fun settingsPage() {
        content.addView(text("Configurações", 25f, ink, true))
        content.addView(panel().apply {
            addView(text("Aparência", 20f, ink, true))
            addView(text("Tema atual: ${prefs.getString("theme", "Azul profundo")}", 14f, muted))
            addView(action("Escolher tema") { settings() })
        })
        content.addView(panel().apply {
            addView(text("Conexão", 20f, ink, true))
            addView(text(message, 14f, muted))
            addView(action("Atualizar conexão") { connect() })
        })
        content.addView(action("Adicionar à tela inicial") { requestHomeShortcut(true) })
    }
    private fun requestHomeShortcut(manual: Boolean) {
        // Launchers decide where icons go and require user confirmation.
        prefs.edit().putBoolean("homeShortcutRequested", true).apply()
        val manager = getSystemService(ShortcutManager::class.java)
        try {
            if (manager.pinnedShortcuts.any { it.id == "driveflow-home" }) {
                if (manual) Toast.makeText(this, "O atalho já está na tela inicial.", Toast.LENGTH_SHORT).show()
                return
            }
            if (!manager.isRequestPinShortcutSupported) {
                if (manual) Toast.makeText(this, "Arraste o ícone do DriveFlow da lista de aplicativos para a tela inicial.", Toast.LENGTH_LONG).show()
                return
            }
            val shortcut = ShortcutInfo.Builder(this, "driveflow-home")
                .setShortLabel("DriveFlow")
                .setLongLabel("DriveFlow Monitor")
                .setIcon(Icon.createWithResource(this, R.mipmap.ic_launcher))
                .setIntent(Intent(this, MainActivity::class.java).setAction(Intent.ACTION_VIEW)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
                .build()
            if (!manager.requestPinShortcut(shortcut, null) && manual) {
                Toast.makeText(this, "Não foi possível solicitar o atalho. Tente adicioná-lo pela lista de aplicativos.", Toast.LENGTH_LONG).show()
            }
        } catch (_: RuntimeException) {
            if (manual) Toast.makeText(this, "Não foi possível adicionar o atalho neste momento.", Toast.LENGTH_LONG).show()
        }
    }
    private fun number(doc: DocumentSnapshot, key: String): Double = (doc.get(key) as? Number)?.toDouble() ?: 0.0
    private fun statusLine(parent: LinearLayout, doc: DocumentSnapshot?) {
        val status = doc?.getString("status") ?: ""
        val stale = MonitorModel.stale(status, doc?.getTimestamp("last_update")?.toDate()?.time, System.currentTimeMillis(),
            (doc?.get("update_interval_seconds") as? Number)?.toDouble() ?: 5.0)
        val label = when {
            doc == null -> "Carregando / acesso indisponível"
            !doc.exists() -> "Aguardando publicação do Windows"
            stale -> "Sem atualização • conexão a verificar"
            else -> MonitorModel.statuses[status] ?: "Estado desconhecido"
        }
        parent.addView(text("●  $label", 14f, if (status == "error" || stale) Color.parseColor("#ffb481") else color(3), true))
        if (doc?.metadata?.isFromCache == true) parent.addView(text("Dados salvos • aguardando conexão", 12f, muted))
    }
    private fun progress(parent: LinearLayout, doc: DocumentSnapshot) {
        val percent = number(doc, "progress_percent").takeIf { it.isFinite() }?.coerceIn(0.0, 100.0) ?: 0.0
        parent.addView(text(String.format(Locale.forLanguageTag("pt-BR"), "%.1f%%", percent), 30f, ink, true))
        parent.addView(ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 1000; progress = (percent * 10).toInt()
            progressTintList = ColorStateList.valueOf(color(3))
            progressBackgroundTintList = ColorStateList.valueOf(color(2))
        }, LinearLayout.LayoutParams(-1, dp(8)))
    }
    private fun details(id: String) {
        content.addView(action("‹  Computadores") { selected = null; render() })
        content.addView(text(names[id] ?: id, 28f, ink, true))
        val doc = states[id]
        content.addView(panel().apply {
            statusLine(this, doc)
            if (doc?.exists() == true) {
                progress(this, doc)
                addView(text(doc.getString("current_file") ?: "", 18f, ink, true))
                addView(text("${MonitorModel.bytes(number(doc, "bytes_uploaded"))} de ${MonitorModel.bytes(number(doc, "current_file_size"))}", 14f, muted))
                addView(text("Velocidade: ${MonitorModel.bytes(number(doc, "upload_speed"))}/s"))
                addView(text("Tempo restante: ${MonitorModel.duration((doc.get("estimated_time_remaining") as? Number)?.toDouble())}"))
                addView(text("Fila: ${doc.getLong("queue_remaining") ?: 0} restantes / ${doc.getLong("queue_total") ?: 0} registros"))
                addView(text("Destino: ${doc.getString("current_destination") ?: "—"}"))
                val date = doc.getTimestamp("last_update")?.toDate()
                addView(text("Atualizado: ${date?.let { SimpleDateFormat("dd/MM HH:mm:ss", Locale.getDefault()).format(it) } ?: "—"}", 12f, muted))
                addView(text("Windows v${doc.getString("software_version") ?: "—"}", 12f, muted))
            }
        })
        content.addView(text("Acesso somente de leitura. O envio é controlado pelo computador.", 13f, muted))
        content.addView(action("Desvincular computador") {
            AlertDialog.Builder(this).setTitle("Desvincular?").setMessage("Este celular deixará de acompanhar ${names[id]}.")
                .setNegativeButton("Voltar", null).setPositiveButton("Desvincular") { _, _ ->
                    val uid = auth.currentUser?.uid ?: return@setPositiveButton
                    val batch = db.batch()
                    batch.delete(db.document("readers/$uid/computers/$id"))
                    batch.delete(db.document("computers/$id/readers/$uid"))
                    batch.commit()
                        .addOnSuccessListener { selected = null; render() }.addOnFailureListener { fail("Não foi possível desvincular. Tente novamente.") }
                }.show()
        })
    }
    private fun settings() {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), dp(8), dp(24), dp(8)) }
        box.addView(text("Tema", 15f, ink, true))
        val spinner = Spinner(this)
        val options = themes.keys.toList()
        spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, options)
        spinner.setSelection(options.indexOf(prefs.getString("theme", "Azul profundo")).coerceAtLeast(0))
        box.addView(spinner)
        box.addView(text("Acompanhe os uploads com o aplicativo aberto. Notificações não estão disponíveis nesta versão.", 13f, muted))
        AlertDialog.Builder(this).setTitle("Preferências").setView(box).setNegativeButton("Voltar", null)
            .setPositiveButton("Salvar") { _, _ ->
                prefs.edit().putString("theme", options[spinner.selectedItemPosition]).apply()
                render(); connect()
            }.show()
    }
    private fun scan() {
        val options = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).enableAutoZoom().build()
        GmsBarcodeScanning.getClient(this, options).startScan().addOnSuccessListener { result ->
            try {
                val raw = result.rawValue ?: error("empty")
                require(raw.length < 2048)
                val qr = JSONObject(raw)
                require(qr.getInt("version") == 2 && qr.getString("type") == "driveflow-pair")
                require(qr.getString("project") == FirebaseApp.getInstance().options.projectId)
                val token = qr.getString("token")
                require(MonitorModel.validToken(token))
                AlertDialog.Builder(this).setTitle("Adicionar computador?")
                    .setMessage("Vincular ${qr.optString("name", "este computador").take(100)} a este celular?")
                    .setNegativeButton("Cancelar", null).setPositiveButton("Conectar") { _, _ -> pair(token) }.show()
            } catch (_: Exception) { fail("QR code inválido ou de outro projeto. Gere um novo no DriveFlow do Windows.") }
        }.addOnFailureListener { fail("Não foi possível abrir o scanner. Verifique a internet e atualize o Google Play Services.") }
    }
    private fun pair(token: String) {
        val uid = auth.currentUser?.uid ?: return
        pairing = true; render()
        val hash = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it.toInt() and 255) }
        val codeRef = db.document("pairing_codes/$hash")
        db.runTransaction { transaction ->
            val code = transaction.get(codeRef)
            val id = code.getString("computer_id") ?: error("invalid code")
            require(Regex("[A-Za-z0-9_-]{1,128}").matches(id))
            val link = db.document("readers/$uid/computers/$id")
            val existing = transaction.get(link)
            if (code.getString("usedBy") == uid && existing.exists()) return@runTransaction id
            require(code.getString("usedBy") == null && code.getString("protocol") == "spark-v2")
            if (existing.exists()) return@runTransaction id
            transaction.update(codeRef, mapOf("usedBy" to uid, "usedAt" to FieldValue.serverTimestamp()))
            transaction.set(link, mapOf("computer_name" to (code.getString("computer_name") ?: id),
                "codeHash" to hash, "pairedAt" to FieldValue.serverTimestamp()))
            transaction.set(db.document("computers/$id/readers/$uid"), mapOf("deviceName" to Build.MODEL.take(100),
                "codeHash" to hash, "pairedAt" to FieldValue.serverTimestamp()))
            id
        }
            .addOnSuccessListener { result ->
                pairing = false
                selected = result
                settingsTab = false
                message = "Computador vinculado"; render()
            }.addOnFailureListener { error ->
                pairing = false
                fail("Não foi possível vincular. Gere outro QR code e verifique a conexão. As regras de pareamento precisam estar publicadas no Firebase.")
            }
    }
    private fun fail(value: String) {
        if (isDestroyed || !foreground) return
        message = value; render()
        Toast.makeText(this, value, Toast.LENGTH_LONG).show()
    }
}
