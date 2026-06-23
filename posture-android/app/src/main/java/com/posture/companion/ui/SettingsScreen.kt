package com.posture.companion.ui

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.NetworkCheck
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Vibration
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.posture.companion.SensorRate
import com.posture.companion.SensorViewModel
import com.posture.companion.ui.theme.Background
import com.posture.companion.ui.theme.Blue400
import com.posture.companion.ui.theme.GreenConnected
import com.posture.companion.ui.theme.Surface
import com.posture.companion.ui.theme.SurfaceHigh
import com.posture.companion.ui.theme.SurfaceVar
import com.posture.companion.ui.theme.TextPrimary
import com.posture.companion.ui.theme.TextSecondary
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: SensorViewModel,
    onNavigateBack: () -> Unit,
    onTestVibration: () -> Unit
) {
    val serverIp          by viewModel.serverIp.collectAsState()
    val serverPort        by viewModel.serverPort.collectAsState()
    val vibrationIntensity by viewModel.vibrationIntensity.collectAsState()
    val sensorRate        by viewModel.sensorRate.collectAsState()

    // Local edit state — we only persist on Save
    var editIp        by remember(serverIp)   { mutableStateOf(serverIp) }
    var editPort      by remember(serverPort) { mutableStateOf(serverPort.toString()) }
    var editIntensity by remember(vibrationIntensity) { mutableStateOf(vibrationIntensity.toFloat()) }
    var editRate      by remember(sensorRate) { mutableStateOf(sensorRate) }

    var ipError       by remember { mutableStateOf(false) }
    var portError     by remember { mutableStateOf(false) }

    val scope             = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Settings",
                        style = MaterialTheme.typography.headlineSmall.copy(
                            color = TextPrimary,
                            fontWeight = FontWeight.SemiBold
                        )
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Back",
                            tint = TextSecondary
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Background)
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {

            // ── Network Settings ────────────────────────────────────────────
            SettingsSection(
                title = "Network",
                icon  = { Icon(Icons.Default.NetworkCheck, null, tint = Blue400, modifier = Modifier.size(18.dp)) }
            ) {
                // IP address field
                OutlinedTextField(
                    value = editIp,
                    onValueChange = { new ->
                        editIp  = new
                        ipError = new.isBlank()
                    },
                    label    = { Text("Server IP Address") },
                    isError  = ipError,
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Uri,
                        imeAction    = ImeAction.Next
                    ),
                    colors = settingsTextFieldColors(),
                    modifier = Modifier.fillMaxWidth(),
                    supportingText = {
                        if (ipError) Text("IP address cannot be empty", color = MaterialTheme.colorScheme.error)
                        else Text("e.g. 192.168.1.100", color = TextSecondary)
                    }
                )

                Spacer(modifier = Modifier.height(4.dp))

                // Port field
                OutlinedTextField(
                    value = editPort,
                    onValueChange = { new ->
                        editPort  = new.filter { it.isDigit() }
                        portError = editPort.isBlank() || (editPort.toIntOrNull() ?: 0) !in 1..65535
                    },
                    label    = { Text("Port") },
                    isError  = portError,
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Number,
                        imeAction    = ImeAction.Done
                    ),
                    colors = settingsTextFieldColors(),
                    modifier = Modifier.fillMaxWidth(),
                    supportingText = {
                        if (portError) Text("Port must be 1–65535", color = MaterialTheme.colorScheme.error)
                        else Text("Default: 8765", color = TextSecondary)
                    }
                )
            }

            // ── Sensor Rate ────────────────────────────────────────────────
            SettingsSection(
                title = "Sensor Rate",
                icon  = { Icon(Icons.Default.Speed, null, tint = Blue400, modifier = Modifier.size(18.dp)) }
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    SensorRate.entries.forEach { rate ->
                        FilterChip(
                            selected = editRate == rate,
                            onClick  = { editRate = rate },
                            label    = { Text(rate.label.split(" ").first()) },
                            modifier = Modifier.weight(1f),
                            colors   = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = Blue400.copy(alpha = 0.2f),
                                selectedLabelColor     = Blue400
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled  = true,
                                selected = editRate == rate,
                                selectedBorderColor = Blue400,
                                borderColor = SurfaceHigh
                            )
                        )
                    }
                }
                Text(
                    text = "Selected: ${editRate.label}",
                    style = MaterialTheme.typography.bodySmall.copy(color = TextSecondary),
                    modifier = Modifier.padding(top = 4.dp)
                )
            }

            // ── Vibration ──────────────────────────────────────────────────
            SettingsSection(
                title = "Haptic Feedback",
                icon  = { Icon(Icons.Default.Vibration, null, tint = Blue400, modifier = Modifier.size(18.dp)) }
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Vibration Intensity",
                        style = MaterialTheme.typography.bodyMedium.copy(color = TextPrimary)
                    )
                    Text(
                        text = "${editIntensity.toInt()}%",
                        style = MaterialTheme.typography.labelLarge.copy(
                            color = Blue400,
                            fontWeight = FontWeight.Bold
                        )
                    )
                }
                Slider(
                    value = editIntensity,
                    onValueChange = { editIntensity = it },
                    valueRange = 0f..100f,
                    steps = 9,
                    colors = SliderDefaults.colors(
                        thumbColor        = Blue400,
                        activeTrackColor  = Blue400,
                        inactiveTrackColor = SurfaceHigh
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(4.dp))

                OutlinedButton(
                    onClick = onTestVibration,
                    modifier = Modifier.fillMaxWidth(),
                    colors   = ButtonDefaults.outlinedButtonColors(contentColor = Blue400),
                    border   = BorderStroke(1.dp, Blue400)
                ) {
                    Icon(Icons.Default.Vibration, null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Test Vibration")
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ── Save Button ────────────────────────────────────────────────
            Button(
                onClick = {
                    ipError   = editIp.isBlank()
                    portError = editPort.isBlank() || (editPort.toIntOrNull() ?: 0) !in 1..65535
                    if (!ipError && !portError) {
                        viewModel.saveSettings(
                            ip        = editIp.trim(),
                            port      = editPort.toInt(),
                            intensity = editIntensity.toInt(),
                            rate      = editRate
                        )
                        scope.launch {
                            snackbarHostState.showSnackbar("Settings saved successfully")
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                shape  = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Blue400)
            ) {
                Icon(Icons.Default.Save, null, modifier = Modifier.size(20.dp))
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text  = "Save Settings",
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

// ─── Reusable settings card section ──────────────────────────────────────────

@Composable
private fun SettingsSection(
    title: String,
    icon: @Composable () -> Unit,
    content: @Composable () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .animateContentSize(),
        colors = CardDefaults.cardColors(containerColor = Surface),
        shape  = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, SurfaceHigh)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                icon()
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium.copy(
                        color = TextPrimary,
                        fontWeight = FontWeight.SemiBold
                    )
                )
            }
            Spacer(modifier = Modifier.height(14.dp))
            content()
        }
    }
}

@Composable
private fun settingsTextFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor   = Blue400,
    unfocusedBorderColor = SurfaceHigh,
    focusedLabelColor    = Blue400,
    unfocusedLabelColor  = TextSecondary,
    focusedTextColor     = TextPrimary,
    unfocusedTextColor   = TextPrimary,
    cursorColor          = Blue400
)
