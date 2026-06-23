package com.posture.companion.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// PostureGuard always uses dark theme — matches the laptop companion UI
private val DarkColorScheme = darkColorScheme(
    primary               = Blue400,
    onPrimary             = OnPrimary,
    primaryContainer      = BlueGlow,
    onPrimaryContainer    = Blue200,

    secondary             = AccentPurple,
    onSecondary           = OnPrimary,
    secondaryContainer    = Color(0xFF2D2140),
    onSecondaryContainer  = AccentPurple,

    tertiary              = AccentOrange,
    onTertiary            = OnPrimary,

    background            = Background,
    onBackground          = TextPrimary,

    surface               = Surface,
    onSurface             = TextPrimary,
    surfaceVariant        = SurfaceVar,
    onSurfaceVariant      = TextSecondary,

    outline               = SurfaceHigh,
    outlineVariant        = TextMuted,

    error                 = RedError,
    onError               = OnPrimary,
    errorContainer        = RedErrorDim,
    onErrorContainer      = RedError,

    inverseSurface        = TextPrimary,
    inverseOnSurface      = Background,
    inversePrimary        = Blue400
)

@Composable
fun PostureCompanionTheme(
    content: @Composable () -> Unit
) {
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor     = Background.toArgb()
            window.navigationBarColor = Background.toArgb()
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars     = false
                isAppearanceLightNavigationBars = false
            }
        }
    }

    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography  = AppTypography,
        content     = content
    )
}
