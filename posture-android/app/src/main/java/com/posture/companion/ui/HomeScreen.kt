package com.posture.companion.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Sensors
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.posture.companion.ConnectionStatus
import com.posture.companion.SensorViewModel
import com.posture.companion.ui.theme.AmberConnecting
import com.posture.companion.ui.theme.AmberConnectingDim
import com.posture.companion.ui.theme.Background
import com.posture.companion.ui.theme.Blue400
import com.posture.companion.ui.theme.BlueGlow
import com.posture.companion.ui.theme.GreenConnected
import com.posture.companion.ui.theme.GreenConnectedDim
import com.posture.companion.ui.theme.RedError
import com.posture.companion.ui.theme.RedErrorDim
import com.posture.companion.ui.theme.Surface
import com.posture.companion.ui.theme.SurfaceHigh
import com.posture.companion.ui.theme.SurfaceVar
import com.posture.companion.ui.theme.TextMuted
import com.posture.companion.ui.theme.TextPrimary
import com.posture.companion.ui.theme.TextSecondary
import kotlin.math.abs

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    viewModel: SensorViewModel,
    onNavigateToSettings: () -> Unit,
    onNavigateToStatus: () -> Unit,
    onStartService: (String, Int) -> Unit,
    onStopService: () -> Unit
) {
    val connectionStatus by viewModel.connectionStatus.collectAsState()
    val currentPitch     by viewModel.currentPitch.collectAsState()
    val currentRoll      by viewModel.currentRoll.collectAsState()
    val serverIp         by viewModel.serverIp.collectAsState()
    val serverPort       by viewModel.serverPort.collectAsState()
    val isStreaming      by viewModel.isStreaming.collectAsState()
    val postureLabel     by viewModel.postureLabel.collectAsState()
    val packetsSent      by viewModel.packetsSent.collectAsState()
    val errorMessage     by viewModel.errorMessage.collectAsState()

    val snackbarHostState = remember { SnackbarHostState() }

    // Show errors in snackbar
    LaunchedEffect(errorMessage) {
        errorMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { /* blank — we use our own hero header */ },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Background
                ),
                actions = {
                    IconButton(onClick = onNavigateToStatus) {
                        Icon(
                            imageVector = Icons.Default.Analytics,
                            contentDescription = "Status",
                            tint = TextSecondary
                        )
                    }
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = "Settings",
                            tint = TextSecondary
                        )
                    }
                }
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
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {

            // ── App Header ─────────────────────────────────────────────────
            AppHeader()

            // ── Connection Status Chip ──────────────────────────────────────
            ConnectionStatusChip(status = connectionStatus)

            // ── Big animated start / stop button ───────────────────────────
            StreamButton(
                isStreaming = isStreaming,
                connectionStatus = connectionStatus,
                onStart = { onStartService(serverIp, serverPort) },
                onStop  = onStopService
            )

            // ── Server target ───────────────────────────────────────────────
            ServerTargetCard(ip = serverIp, port = serverPort)

            // ── Angle Display Cards ─────────────────────────────────────────
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                AngleCard(
                    label = "Pitch",
                    value = currentPitch,
                    modifier = Modifier.weight(1f),
                    warningThreshold = 20f
                )
                AngleCard(
                    label = "Roll",
                    value = currentRoll,
                    modifier = Modifier.weight(1f),
                    warningThreshold = 15f
                )
            }

            // ── Posture Label ───────────────────────────────────────────────
            PostureLabelCard(
                label = postureLabel,
                packetsSent = packetsSent,
                isStreaming = isStreaming
            )

            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

// ─── Sub-composables ──────────────────────────────────────────────────────────

@Composable
private fun AppHeader() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(vertical = 8.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = Icons.Default.Sensors,
                contentDescription = null,
                tint = Blue400,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.width(10.dp))
            Text(
                text = "PostureGuard",
                style = MaterialTheme.typography.displaySmall.copy(
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = "Smart Posture Correction System",
            style = MaterialTheme.typography.bodyMedium.copy(color = TextSecondary),
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun ConnectionStatusChip(status: ConnectionStatus) {
    val (label, bgColor, contentColor, icon) = when (status) {
        ConnectionStatus.CONNECTED    -> Quad("Connected",    GreenConnectedDim, GreenConnected,  Icons.Default.CheckCircle)
        ConnectionStatus.CONNECTING   -> Quad("Connecting…",  AmberConnectingDim, AmberConnecting, null)
        ConnectionStatus.ERROR        -> Quad("Error",         RedErrorDim,        RedError,        Icons.Default.Error)
        ConnectionStatus.DISCONNECTED -> Quad("Disconnected",  SurfaceVar,         TextSecondary,   Icons.Default.WifiOff)
    }

    val animatedBg by animateColorAsState(bgColor, label = "chipBg")
    val animatedFg by animateColorAsState(contentColor, label = "chipFg")

    Surface(
        shape  = RoundedCornerShape(50),
        color  = animatedBg,
        modifier = Modifier.border(1.dp, animatedFg.copy(alpha = 0.4f), RoundedCornerShape(50))
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            if (status == ConnectionStatus.CONNECTING) {
                CircularProgressIndicator(
                    modifier = Modifier.size(14.dp),
                    color = animatedFg,
                    strokeWidth = 2.dp
                )
            } else if (icon != null) {
                Icon(imageVector = icon, contentDescription = null, tint = animatedFg, modifier = Modifier.size(14.dp))
            }
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium.copy(color = animatedFg, fontWeight = FontWeight.SemiBold)
            )
        }
    }
}

@Composable
private fun StreamButton(
    isStreaming: Boolean,
    connectionStatus: ConnectionStatus,
    onStart: () -> Unit,
    onStop: () -> Unit
) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")

    // Pulsing ring — only visible while connected
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue  = 1.25f,
        animationSpec = infiniteRepeatable(
            animation  = tween(900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseScale"
    )
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.5f,
        targetValue  = 0f,
        animationSpec = infiniteRepeatable(
            animation  = tween(900, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseAlpha"
    )

    val buttonColor by animateColorAsState(
        targetValue = when (connectionStatus) {
            ConnectionStatus.CONNECTED  -> GreenConnected
            ConnectionStatus.ERROR      -> RedError
            ConnectionStatus.CONNECTING -> AmberConnecting
            else                        -> Blue400
        },
        animationSpec = tween(400),
        label = "btnColor"
    )
    val buttonScale by animateFloatAsState(
        targetValue = if (isStreaming) 1f else 0.95f,
        animationSpec = spring(stiffness = Spring.StiffnessMediumLow),
        label = "btnScale"
    )

    Box(
        contentAlignment = Alignment.Center,
        modifier = Modifier
            .padding(vertical = 16.dp)
            .size(180.dp)
    ) {
        // Pulsing outer ring
        if (connectionStatus == ConnectionStatus.CONNECTED) {
            Box(
                modifier = Modifier
                    .size(180.dp)
                    .scale(pulseScale)
                    .clip(CircleShape)
                    .background(buttonColor.copy(alpha = pulseAlpha))
            )
        }

        // Main button
        Button(
            onClick = if (isStreaming) onStop else onStart,
            modifier = Modifier
                .size(140.dp)
                .scale(buttonScale),
            shape = CircleShape,
            colors = ButtonDefaults.buttonColors(
                containerColor = buttonColor
            ),
            elevation = ButtonDefaults.buttonElevation(
                defaultElevation  = 8.dp,
                pressedElevation  = 2.dp
            )
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(
                    imageVector = if (isStreaming) Icons.Default.Stop else Icons.Default.PlayArrow,
                    contentDescription = if (isStreaming) "Stop" else "Start",
                    modifier = Modifier.size(40.dp),
                    tint = Color.White
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = if (isStreaming) "STOP" else "START",
                    style = MaterialTheme.typography.labelLarge.copy(
                        color = Color.White,
                        fontWeight = FontWeight.Bold
                    )
                )
            }
        }
    }
}

@Composable
private fun ServerTargetCard(ip: String, port: Int) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Surface),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, SurfaceHigh)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                imageVector = Icons.Default.Wifi,
                contentDescription = null,
                tint = Blue400,
                modifier = Modifier.size(20.dp)
            )
            Column {
                Text(
                    text = "Server Target",
                    style = MaterialTheme.typography.labelSmall.copy(color = TextSecondary)
                )
                Text(
                    text = "$ip:$port",
                    style = MaterialTheme.typography.bodyMedium.copy(
                        color = TextPrimary,
                        fontWeight = FontWeight.SemiBold
                    )
                )
            }
        }
    }
}

@Composable
private fun AngleCard(
    label: String,
    value: Float,
    modifier: Modifier = Modifier,
    warningThreshold: Float = 20f
) {
    val isWarning = abs(value) > warningThreshold
    val valueColor by animateColorAsState(
        targetValue = if (isWarning) RedError else GreenConnected,
        animationSpec = tween(300),
        label = "angleColor"
    )
    val cardBorder by animateColorAsState(
        targetValue = if (isWarning) RedError.copy(alpha = 0.5f) else SurfaceHigh,
        animationSpec = tween(300),
        label = "angleBorder"
    )

    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = Surface),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, cardBorder)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium.copy(color = TextSecondary)
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = String.format("%.1f°", value),
                style = MaterialTheme.typography.headlineMedium.copy(
                    color = valueColor,
                    fontWeight = FontWeight.Bold
                )
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = if (isWarning) "⚠ Alert" else "✓ OK",
                style = MaterialTheme.typography.labelSmall.copy(
                    color = valueColor.copy(alpha = 0.8f)
                )
            )
        }
    }
}

@Composable
private fun PostureLabelCard(
    label: String,
    packetsSent: Long,
    isStreaming: Boolean
) {
    val labelColor = when (label) {
        "Good Posture"      -> GreenConnected
        "Leaning Forward"   -> AmberConnecting
        "Leaning Backward"  -> RedError
        else                -> TextSecondary
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Surface),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, SurfaceHigh)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "Posture Status",
                style = MaterialTheme.typography.labelMedium.copy(color = TextSecondary)
            )
            Text(
                text = label,
                style = MaterialTheme.typography.headlineSmall.copy(
                    color = labelColor,
                    fontWeight = FontWeight.Bold
                )
            )
            if (isStreaming) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(GreenConnected)
                    )
                    Text(
                        text = "$packetsSent packets streamed",
                        style = MaterialTheme.typography.labelSmall.copy(color = TextMuted)
                    )
                }
            }
        }
    }
}

// Tiny data class for destructuring chip tuples
private data class Quad<A, B, C, D>(val a: A, val b: B, val c: C, val d: D)
private operator fun <A, B, C, D> Quad<A, B, C, D>.component1() = a
private operator fun <A, B, C, D> Quad<A, B, C, D>.component2() = b
private operator fun <A, B, C, D> Quad<A, B, C, D>.component3() = c
private operator fun <A, B, C, D> Quad<A, B, C, D>.component4() = d
