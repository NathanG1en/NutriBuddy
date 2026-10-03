/**
 * Application feature flags.
 */
export const FEATURES = {
  /**
   * Text-to-speech voice narration for chat messages.
   * Disabled by default (false).
   * Can be toggled on via VITE_ENABLE_VOICE=true in .env
   */
  ENABLE_VOICE: import.meta.env.VITE_ENABLE_VOICE === 'true',
} as const;
