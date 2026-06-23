package com.posture.companion

import android.app.Application
import android.util.Log
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

// ─── DataStore extension ───────────────────────────────────────────────────────
private val Application.dataStore: DataStore<Preferences> by preferencesDataStore(name = "posture_settings")

// ─── Connection state enum ────────────────────────────────────────────────────
enum class ConnectionStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    ERROR
}

// ─── Sensor rate enum ─────────────────────────────────────────────────────────
enum class SensorRate(val label: String, val delayUs: Int) {
    HIGH("High (100 Hz)", 10_000),
    MEDIUM("Medium (50 Hz)", 20_000),
    LOW("Low (20 Hz)", 50_000)
}

// ─── ViewModel ────────────────────────────────────────────────────────────────

class SensorViewModel(application: Application) : AndroidViewModel(application) {

    companion object {
        private const val TAG = "SensorViewModel"
        private val KEY_SERVER_IP   = stringPreferencesKey("server_ip")
        private val KEY_SERVER_PORT = intPreferencesKey("server_port")
        private val KEY_VIBRATION_INTENSITY = intPreferencesKey("vibration_intensity")
        private val KEY_SENSOR_RATE = stringPreferencesKey("sensor_rate")

        const val DEFAULT_IP   = "192.168.1.100"
        const val DEFAULT_PORT = 8765
    }

    private val dataStore = application.dataStore

    // ─── Connection status ───────────────────────────────────────────────────
    private val _connectionStatus = MutableStateFlow(ConnectionStatus.DISCONNECTED)
    val connectionStatus: StateFlow<ConnectionStatus> = _connectionStatus.asStateFlow()

    // ─── Sensor angles ────────────────────────────────────────────────────────
    private val _currentPitch = MutableStateFlow(0f)
    val currentPitch: StateFlow<Float> = _currentPitch.asStateFlow()

    private val _currentRoll = MutableStateFlow(0f)
    val currentRoll: StateFlow<Float> = _currentRoll.asStateFlow()

    // ─── Server config ────────────────────────────────────────────────────────
    private val _serverIp = MutableStateFlow(DEFAULT_IP)
    val serverIp: StateFlow<String> = _serverIp.asStateFlow()

    private val _serverPort = MutableStateFlow(DEFAULT_PORT)
    val serverPort: StateFlow<Int> = _serverPort.asStateFlow()

    // ─── UI settings ──────────────────────────────────────────────────────────
    private val _vibrationIntensity = MutableStateFlow(75)  // 0–100
    val vibrationIntensity: StateFlow<Int> = _vibrationIntensity.asStateFlow()

    private val _sensorRate = MutableStateFlow(SensorRate.HIGH)
    val sensorRate: StateFlow<SensorRate> = _sensorRate.asStateFlow()

    // ─── Streaming stats ──────────────────────────────────────────────────────
    private val _packetsSent = MutableStateFlow(0L)
    val packetsSent: StateFlow<Long> = _packetsSent.asStateFlow()

    private val _lastPacketTime = MutableStateFlow(0L)
    val lastPacketTime: StateFlow<Long> = _lastPacketTime.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    // ─── Init — load persisted settings ──────────────────────────────────────
    init {
        viewModelScope.launch {
            dataStore.data.collect { prefs ->
                _serverIp.value          = prefs[KEY_SERVER_IP] ?: DEFAULT_IP
                _serverPort.value        = prefs[KEY_SERVER_PORT] ?: DEFAULT_PORT
                _vibrationIntensity.value = prefs[KEY_VIBRATION_INTENSITY] ?: 75
                val rateName = prefs[KEY_SENSOR_RATE] ?: SensorRate.HIGH.name
                _sensorRate.value = SensorRate.entries.find { it.name == rateName } ?: SensorRate.HIGH
            }
        }
    }

    // ─── Public actions ───────────────────────────────────────────────────────

    fun connect(ip: String, port: Int = DEFAULT_PORT) {
        _serverIp.value = ip
        _serverPort.value = port
        _connectionStatus.value = ConnectionStatus.CONNECTING
        _errorMessage.value = null
        Log.d(TAG, "Connecting to $ip:$port")
    }

    fun onConnected() {
        _connectionStatus.value = ConnectionStatus.CONNECTED
        _errorMessage.value = null
        Log.d(TAG, "Connected successfully")
    }

    fun disconnect() {
        _connectionStatus.value = ConnectionStatus.DISCONNECTED
        _packetsSent.value = 0L
        Log.d(TAG, "Disconnected")
    }

    fun onConnectionError(message: String) {
        _connectionStatus.value = ConnectionStatus.ERROR
        _errorMessage.value = message
        Log.e(TAG, "Connection error: $message")
    }

    /**
     * Called from SensorService (via callback) with the latest filtered angles.
     */
    fun updateFromSensor(pitch: Float, roll: Float) {
        _currentPitch.value = pitch
        _currentRoll.value  = roll
        _packetsSent.value  = _packetsSent.value + 1
        _lastPacketTime.value = System.currentTimeMillis()

        // Auto-transition from CONNECTING to CONNECTED once we receive sensor data
        if (_connectionStatus.value == ConnectionStatus.CONNECTING) {
            _connectionStatus.value = ConnectionStatus.CONNECTED
        }
    }

    // ─── Settings persistence ─────────────────────────────────────────────────

    fun saveSettings(
        ip: String,
        port: Int,
        intensity: Int,
        rate: SensorRate
    ) {
        viewModelScope.launch {
            dataStore.edit { prefs ->
                prefs[KEY_SERVER_IP]           = ip
                prefs[KEY_SERVER_PORT]         = port
                prefs[KEY_VIBRATION_INTENSITY] = intensity
                prefs[KEY_SENSOR_RATE]         = rate.name
            }
            _serverIp.value           = ip
            _serverPort.value         = port
            _vibrationIntensity.value = intensity
            _sensorRate.value         = rate
            Log.d(TAG, "Settings saved: ip=$ip port=$port intensity=$intensity rate=${rate.name}")
        }
    }

    fun updateServerIp(ip: String) {
        _serverIp.value = ip
    }

    fun updateServerPort(port: Int) {
        _serverPort.value = port
    }

    fun updateVibrationIntensity(intensity: Int) {
        _vibrationIntensity.value = intensity
    }

    fun updateSensorRate(rate: SensorRate) {
        _sensorRate.value = rate
    }

    fun clearError() {
        _errorMessage.value = null
    }

    // ─── Derived helpers ──────────────────────────────────────────────────────

    /** True when actively streaming data to the server */
    val isStreaming: StateFlow<Boolean> = connectionStatus.map {
        it == ConnectionStatus.CONNECTED || it == ConnectionStatus.CONNECTING
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)

    /** Human-readable posture label based on pitch */
    val postureLabel: StateFlow<String> = currentPitch.map { pitch ->
        when {
            pitch > 30f  -> "Leaning Forward"
            pitch < -15f -> "Leaning Backward"
            else         -> "Good Posture"
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "Unknown")
}
