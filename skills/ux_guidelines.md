---
name: UX Guidelines
description: Principles for creating a premium User Experience in B.L.A.S.T.
---

# User Experience (UX) Guidelines

## 1. The "Premium" Aesthetic
The user explicitly requested "WOW" factors.
- **Glassmorphism**: Translucent cards with blur.
- **Gradients**: Use warm, vibrant gradients (Orange/Red) for brand identity.
- **Typography**: Clean, sans-serif fonts. Large headers (`4rem`).

## 2. Responsiveness
- **Feedback**: Immediate visual feedback for EVERY action.
  - Button click -> Spinner.
  - Processing -> Progress bar.
  - Success -> Green badge/toast.
- **Latency**: Operations > 0.5s must show a loader.

## 3. Dark Mode First
The interface is optimized for dark mode (`#312e81` background).
- **Contrast**: Text must be high contrast (`#e0e7ff`).
- **Shadows**: Use colored shadows (glows) instead of black shadows for depth.

## 4. Information Architecture
- **Hierarchy**: Most important controls (Upload) at the top.
- **Density**: Use white space liberally. Don't crowd the interface.
- **Tabs**: Group related functionality (e.g., "Settings" vs. "Run").
